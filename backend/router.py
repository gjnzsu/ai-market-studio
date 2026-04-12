import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from backend.models import (
    ChatRequest, ChatResponse,
    HistoricalRatesRequest, HistoricalRatesResponse, DailyRates,
    DashboardConfig, DashboardDataResponse,
    ExportPdfRequest,
)
from backend.agent.agent import run_agent
from backend.connectors.base import ConnectorError
from backend.cache import RateCache
from skills.pdf.pdf_skill import generate as generate_pdf

rate_cache = RateCache()

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """Accept a user message and return an AI-generated reply with FX data."""
    connector = request.app.state.connector
    news_connector = getattr(request.app.state, 'news_connector', None)
    history = [m.model_dump() for m in body.history]

    try:
        result = await run_agent(
            message=body.message,
            history=history,
            connector=connector,
            news_connector=news_connector,
        )
    except ConnectorError as e:
        logger.error("Connector error in /chat: %s", e)
        raise HTTPException(status_code=503, detail="Market data service unavailable.")
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
    """
    Render a chat response as a PDF and return it as a downloadable file.

    Accepts the current chat reply text + structured data from the agent,
    renders a formatted PDF, and returns it as application/pdf.
    """
    try:
        dtype = body.data.get("type", "insight") if body.data else "insight"
        report_type = f"fx-{dtype}"
        generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        pdf_bytes = generate_pdf({
            "report_type": report_type,
            "reply": body.reply,
            "data": body.data or {},
            "tool_used": body.tool_used or "N/A",
            "generated_at": generated_at,
        })
    except Exception as e:
        logger.exception("PDF export failed: %s", e)
        raise HTTPException(status_code=500, detail="PDF generation failed.")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    filename = f"fx-insight-{timestamp}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
