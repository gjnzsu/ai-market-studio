import logging
import time
from typing import Any, Optional

from backend.agents.market_analyst import analyze_market_trends
from backend.connectors.base import MarketDataConnector
from backend.connectors.news_connector import NewsConnectorBase

logger = logging.getLogger(__name__)


def _split_pair(pair: str) -> tuple[str, str]:
    parts = pair.upper().replace("-", "/").split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid currency pair: {pair}")
    return parts[0], parts[1]


async def collect_market_context(
    pairs: Optional[list[str]] = None,
    sources: Optional[list[str]] = None,
    days: Optional[int] = None,
    fred_series_ids: Optional[list[str]] = None,
    query: Optional[str] = None,
    connector: Optional[MarketDataConnector] = None,
    news_connector: Optional[NewsConnectorBase] = None,
    fred_connector=None,
    rag_connector=None,
) -> dict[str, Any]:
    selected = sources or ["rates"]
    context: dict[str, Any] = {}
    warnings: list[dict[str, str]] = []

    if "rates" in selected:
        if connector is None:
            raise ValueError("connector is required for rates context")
        rate_results = []
        for pair in pairs or []:
            base, target = _split_pair(pair)
            rate_results.append(
                await connector.get_exchange_rate(base=base, target=target)
            )
        context["rates"] = rate_results

    if "news" in selected:
        if news_connector is None:
            warnings.append({"source": "news", "error": "News connector not available"})
        else:
            try:
                context["news"] = news_connector.get_fx_news(query=query, max_items=5)
            except Exception as e:
                warnings.append({"source": "news", "error": str(e)})

    if "fred" in selected:
        if fred_connector is None:
            warnings.append({"source": "fred", "error": "FRED connector not available"})
        else:
            try:
                fred_results = []
                for series_id in fred_series_ids or ["DFF"]:
                    result = await fred_connector.get_current_rate(series_id=series_id)
                    fred_results.append(result.model_dump())
                context["fred"] = fred_results
            except Exception as e:
                warnings.append({"source": "fred", "error": str(e)})

    if "research" in selected:
        if rag_connector is None:
            warnings.append(
                {"source": "research", "error": "RAG connector not available"}
            )
        else:
            try:
                context["research"] = await rag_connector.query_research(
                    question=query or "FX market outlook"
                )
            except Exception as e:
                warnings.append({"source": "research", "error": str(e)})

    return {
        "type": "market_context",
        "context": context,
        "warnings": warnings,
        "metadata": {"sources": selected, "pairs": pairs or [], "days": days},
    }


async def analyze_market_context(
    context: Optional[dict[str, Any]] = None,
    pairs: Optional[list[str]] = None,
    analysis_type: str = "trend",
    days: Optional[int] = None,
    connector: Optional[MarketDataConnector] = None,
    **connectors,
) -> dict[str, Any]:
    market_context = context
    if market_context is None:
        market_context = await collect_market_context(
            pairs=pairs,
            sources=["rates"],
            days=days,
            connector=connector,
            **connectors,
        )

    analysis_input = {"data": market_context.get("context", {}).get("rates", [])}
    internal_analysis_type = (
        "correlation" if analysis_type == "economic_relationship" else analysis_type
    )
    if internal_analysis_type == "general":
        internal_analysis_type = "trend"
    analysis = await analyze_market_trends(
        data=analysis_input,
        analysis_type=internal_analysis_type,
    )
    return {
        "type": "market_analysis",
        "context": market_context,
        "analysis": analysis,
        "warnings": market_context.get("warnings", []),
    }


async def generate_market_briefing(
    pairs: list[str],
    focus: Optional[str] = None,
    include_news: bool = True,
    include_fred: bool = False,
    include_research: bool = True,
    fred_series_ids: Optional[list[str]] = None,
    connector: Optional[MarketDataConnector] = None,
    news_connector: Optional[NewsConnectorBase] = None,
    fred_connector=None,
    rag_connector=None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    internal_units = ["collect_market_context", "analyze_market_context"]
    logger.info(
        "workflow_start mode=workflow name=generate_market_briefing units=%s pairs=%s",
        internal_units,
        pairs,
    )
    sources = ["rates"]
    if include_news:
        sources.append("news")
    if include_fred:
        sources.append("fred")
    if include_research:
        sources.append("research")

    try:
        context = await collect_market_context(
            pairs=pairs,
            sources=sources,
            fred_series_ids=fred_series_ids,
            query=focus or " ".join(pairs),
            connector=connector,
            news_connector=news_connector,
            fred_connector=fred_connector,
            rag_connector=rag_connector,
        )
        analysis = await analyze_market_context(context=context, analysis_type="trend")
        result = {
            "type": "market_briefing",
            "pairs": pairs,
            "context": context,
            "analysis": analysis["analysis"],
            "briefing": {
                "summary": "Market briefing context collected and analyzed.",
                "focus": focus,
            },
            "warnings": context.get("warnings", []),
        }
        logger.info(
            "workflow_complete mode=workflow name=generate_market_briefing units=%s latency_ms=%.2f status=success failure_category=none",
            internal_units,
            (time.perf_counter() - started_at) * 1000,
        )
        return result
    except Exception:
        logger.exception(
            "workflow_complete mode=workflow name=generate_market_briefing units=%s latency_ms=%.2f status=failure failure_category=exception",
            internal_units,
            (time.perf_counter() - started_at) * 1000,
        )
        raise
