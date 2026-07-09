import logging
from datetime import UTC, datetime
import httpx
import openai
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response

from backend.config import settings
from backend.models import (
    ChatRequest, ChatResponse,
    HistoricalRatesRequest, HistoricalRatesResponse, DailyRates,
    DashboardConfig, DashboardDataResponse,
    ExportPdfRequest,
)
from backend.agent.agent import run_agent
from backend.attribution import ensure_request_id
from backend.connectors.base import ConnectorError
from backend.cache import RateCache
from backend.exporters.pdf_exporter import generate_insight_pdf

rate_cache = RateCache()

logger = logging.getLogger(__name__)
router = APIRouter()


def _gateway_error_code(exc: openai.APIStatusError) -> str | None:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("code"), str):
            return error["code"]
        if isinstance(body.get("code"), str):
            return body["code"]
    try:
        payload = exc.response.json()
    except Exception:
        return None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("code"), str):
            return error["code"]
        if isinstance(payload.get("code"), str):
            return payload["code"]
    return None


def _is_gateway_safety_error(code: str | None) -> bool:
    return bool(code and "safety" in code)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """Accept a user message and return an AI-generated reply with FX data."""
    import asyncio

    def _workflow_mode_disabled_error() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent workflow mode is disabled.",
        )

    connector = request.app.state.connector
    news_connector = getattr(request.app.state, 'news_connector', None)
    fred_connector = getattr(request.app.state, 'fred_connector', None)
    rag_connector = getattr(request.app.state, 'rag_connector', None)
    history = [m.model_dump() for m in body.history]
    request_id = ensure_request_id(body.client_context)

    try:
        if not settings.enable_agent_workflow_mode:
            raise _workflow_mode_disabled_error()

        timeout_seconds = settings.agent_workflow_timeout_seconds

        result = await asyncio.wait_for(
            run_agent(
                message=body.message,
                history=history,
                connector=connector,
                news_connector=news_connector,
                fred_connector=fred_connector,
                rag_connector=rag_connector,
                agent_mode=body.agent_mode,
                client_context=body.client_context,
                request_id=request_id,
            ),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.error(
            "Request timeout after %ss for message: %s ai_path=gateway",
            settings.agent_workflow_timeout_seconds,
            body.message,
        )
        raise HTTPException(status_code=504, detail="Request timeout - query too complex. Please simplify your question.")
    except HTTPException:
        raise
    except ConnectorError as e:
        logger.error("Connector error in /chat: %s", e)
        raise HTTPException(status_code=503, detail="Market data service unavailable.")
    except openai.APITimeoutError as e:
        logger.error("Gateway timeout in /chat: %s ai_path=gateway", e)
        raise HTTPException(status_code=504, detail="AI gateway timeout.")
    except openai.APIStatusError as e:
        gateway_code = _gateway_error_code(e)
        if _is_gateway_safety_error(gateway_code):
            logger.error(
                "Gateway safety policy denied /chat: code=%s status=%s ai_path=gateway",
                gateway_code,
                e.status_code,
            )
            if gateway_code and gateway_code.startswith("prompt_"):
                raise HTTPException(
                    status_code=400,
                    detail="AI gateway safety policy rejected the prompt.",
                )
            raise HTTPException(
                status_code=502,
                detail="AI gateway safety policy blocked the model response.",
            )
        logger.error("Gateway OpenAI SDK error in /chat: %s ai_path=gateway", e)
        raise HTTPException(status_code=503, detail="AI gateway unavailable.")
    except openai.APIConnectionError as e:
        logger.error("Gateway OpenAI SDK error in /chat: %s ai_path=gateway", e)
        raise HTTPException(status_code=503, detail="AI gateway unavailable.")
    except httpx.TimeoutException as e:
        logger.error("Gateway timeout in /chat: %s ai_path=gateway", e)
        raise HTTPException(status_code=504, detail="AI gateway timeout.")
    except httpx.HTTPError as e:
        logger.error("Gateway transport error in /chat: %s ai_path=gateway", e)
        raise HTTPException(status_code=503, detail="AI gateway unavailable.")
    except Exception as e:
        logger.exception("Unexpected error in /chat: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error.")

    return ChatResponse(
        reply=result["reply"],
        data=result["data"],
        tool_used=result["tool_used"],
    )


@router.post("/rates/historical", response_model=HistoricalRatesResponse)
async def get_historical_rates(
    request: Request, body: HistoricalRatesRequest
) -> HistoricalRatesResponse:
    """Return daily FX rates for a date range. Cached with TTL=300s."""
    connector = request.app.state.connector
    hit = rate_cache.get(body.base, body.targets, body.start_date, body.end_date)
    if hit:
        cached_resp = HistoricalRatesResponse(
            base=hit.base,
            start_date=hit.start_date,
            end_date=hit.end_date,
            series=hit.series,
            cached=True,
        )
        return cached_resp
    try:
        raw = await connector.get_historical_rates(
            body.base, body.targets, body.start_date, body.end_date
        )
    except ConnectorError as e:
        raise HTTPException(status_code=502, detail=str(e))
    series = [
        DailyRates(date=d, rates=raw[d]) for d in sorted(raw.keys())
    ]
    resp = HistoricalRatesResponse(
        base=body.base,
        start_date=body.start_date,
        end_date=body.end_date,
        series=series,
        cached=False,
    )
    rate_cache.set(body.base, body.targets, body.start_date, body.end_date, resp)
    return resp


@router.post("/dashboard", response_model=DashboardDataResponse)
async def get_dashboard_data(
    request: Request, config: DashboardConfig
) -> DashboardDataResponse:
    """Batch-fetch data for all dashboard panels. Reuses cache across panels."""
    connector = request.app.state.connector
    panels_out = []
    for panel in config.panels:
        hit = rate_cache.get(
            panel.base, panel.targets, panel.start_date, panel.end_date
        )
        if hit:
            panels_out.append({
                "panel_id": panel.panel_id,
                "panel_type": panel.panel_type,
                "data": hit,
            })
            continue
        try:
            raw = await connector.get_historical_rates(
                panel.base, panel.targets, panel.start_date, panel.end_date
            )
        except ConnectorError as e:
            raise HTTPException(status_code=502, detail=str(e))
        series = [DailyRates(date=d, rates=raw[d]) for d in sorted(raw.keys())]
        resp = HistoricalRatesResponse(
            base=panel.base,
            start_date=panel.start_date,
            end_date=panel.end_date,
            series=series,
            cached=False,
        )
        rate_cache.set(
            panel.base, panel.targets, panel.start_date, panel.end_date, resp
        )
        panels_out.append({
            "panel_id": panel.panel_id,
            "panel_type": panel.panel_type,
            "data": resp,
        })
    return DashboardDataResponse(
        dashboard_id=config.dashboard_id,
        panels=panels_out,
    )


@router.post("/export/pdf")
async def export_pdf(body: ExportPdfRequest) -> Response:
    """Export chat response to PDF."""
    try:
        pdf_bytes = generate_insight_pdf(
            reply=body.reply,
            data=body.data,
            tool_used=body.tool_used,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="fx-insight-{datetime.now(UTC).strftime("%Y%m%d-%H%M%S")}.pdf"'
            }
        )
    except Exception as e:
        logger.exception("Error generating PDF: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate PDF")

