import logging
import time
from datetime import date as date_type, timedelta
from typing import Any, Optional

from backend.agents.market_analyst import analyze_market_trends
from backend.agent.financial_playbooks import (
    has_runtime_profile,
    select_playbook,
    synthetic_sources_for_playbook,
)
from backend.agent.synthetic_specialist_data import (
    build_fx_carry_metrics,
    get_synthetic_forward_curve,
    get_synthetic_implied_volatility,
)
from backend.connectors.base import MarketDataConnector, UnsupportedPairError
from backend.connectors.news_connector import NewsConnectorBase

logger = logging.getLogger(__name__)


def _split_pair(pair: str) -> tuple[str, str]:
    normalized = pair.upper().replace("-", "/")
    if "/" not in normalized and len(normalized) == 6:
        normalized = f"{normalized[:3]}/{normalized[3:]}"
    parts = normalized.split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid currency pair: {pair}")
    return parts[0], parts[1]


def _historical_window(days: Optional[int]) -> tuple[str, str] | None:
    if days is None or days <= 1:
        return None
    lookback_days = max(2, min(int(days), 30))
    end = date_type.today()
    start = end - timedelta(days=lookback_days - 1)
    return start.isoformat(), end.isoformat()


def _historical_payload(
    pair: str,
    base: str,
    target: str,
    raw: dict[str, dict[str, float]],
) -> dict[str, Any]:
    sorted_dates = sorted(raw.keys())
    return {
        "pair": pair.upper().replace("-", "/"),
        "base": base,
        "target": target,
        "start_date": sorted_dates[0] if sorted_dates else None,
        "end_date": sorted_dates[-1] if sorted_dates else None,
        "series": [
            {"date": day, "rate": raw[day].get(target)}
            for day in sorted_dates
            if raw[day].get(target) is not None
        ],
        "source": "mock",
    }


def _build_pair_series_analysis(
    historical_rates: list[dict[str, Any]],
    analysis_type: str,
) -> dict[str, Any] | None:
    pair_results = []
    for history in historical_rates:
        series = [
            point
            for point in history.get("series", [])
            if isinstance(point.get("rate"), (int, float))
        ]
        if len(series) < 2:
            continue
        rates = [float(point["rate"]) for point in series]
        first_rate = rates[0]
        last_rate = rates[-1]
        change_pct = ((last_rate - first_rate) / first_rate) * 100 if first_rate else 0.0
        mean_rate = sum(rates) / len(rates)
        variance = sum((rate - mean_rate) ** 2 for rate in rates) / (len(rates) - 1)
        volatility = variance ** 0.5
        volatility_pct = (volatility / mean_rate) * 100 if mean_rate else 0.0
        if change_pct > 0.5:
            trend_direction = "uptrend"
        elif change_pct < -0.5:
            trend_direction = "downtrend"
        else:
            trend_direction = "sideways"
        pair_results.append(
            {
                "pair": history.get("pair"),
                "start_date": history.get("start_date"),
                "end_date": history.get("end_date"),
                "observations": len(series),
                "first_rate": round(first_rate, 6),
                "last_rate": round(last_rate, 6),
                "change_pct": round(change_pct, 2),
                "trend_direction": trend_direction,
                "volatility": round(volatility, 6),
                "volatility_pct": round(volatility_pct, 2),
            }
        )
    if not pair_results:
        return None
    return {
        "analysis_type": analysis_type,
        "pairs": pair_results,
        "summary": "Pair-specific analysis generated from historical mock FX series.",
    }


def _is_broad_news_query(query: Optional[str]) -> bool:
    if not query:
        return False
    terms = {"fx", "foreign exchange", "currency", "currencies", "market", "news", "latest"}
    lowered = query.lower()
    return any(term in lowered for term in terms)


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
        historical_results = []
        history_window = _historical_window(days)
        for pair in pairs or []:
            try:
                base, target = _split_pair(pair)
                rate_results.append(
                    await connector.get_exchange_rate(base=base, target=target)
                )
                if history_window is not None:
                    raw_history = await connector.get_historical_rates(
                        base=base,
                        targets=[target],
                        start_date=history_window[0],
                        end_date=history_window[1],
                    )
                    historical_results.append(
                        _historical_payload(pair, base, target, raw_history)
                    )
            except UnsupportedPairError as e:
                pair_label = "/".join(_split_pair(pair)) if len(pair) == 6 else pair
                warnings.append(
                    {"source": "rates", "error": f"{pair_label}: {str(e)}"}
                )
        context["rates"] = rate_results
        if historical_results:
            context["historical_rates"] = historical_results

    if "news" in selected:
        if news_connector is None:
            warnings.append({"source": "news", "error": "News connector not available"})
        else:
            try:
                news_items = news_connector.get_fx_news(query=query, max_items=5)
                if not news_items and _is_broad_news_query(query):
                    news_items = news_connector.get_fx_news(query=None, max_items=5)
                context["news"] = news_items
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
    if (
        market_context is None
        or not isinstance(market_context, dict)
        or market_context.get("type") != "market_context"
        or not isinstance(market_context.get("context"), dict)
    ):
        market_context = await collect_market_context(
            pairs=pairs,
            sources=["rates"],
            days=days,
            connector=connector,
            **connectors,
        )

    analysis_input = {"data": market_context.get("context", {}).get("rates", [])}
    historical_analysis = _build_pair_series_analysis(
        market_context.get("context", {}).get("historical_rates", []),
        analysis_type,
    )
    if historical_analysis is not None:
        return {
            "type": "market_analysis",
            "context": market_context,
            "analysis": historical_analysis,
            "warnings": market_context.get("warnings", []),
        }
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
    playbook: Optional[str] = None,
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
    selected_playbook = select_playbook(explicit=playbook, focus=focus)
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
        available_sources = list(context.get("context", {}).keys())
        specialist_data = None
        carry_metrics = None
        synthetic_sources: list[str] = []
        if has_runtime_profile(selected_playbook, "demo_synthetic_fx"):
            rate_context = context.get("context", {}).get("rates", [])
            if rate_context:
                primary_rate = rate_context[0]
                pair = f"{primary_rate['base']}/{primary_rate['target']}"
                spot_rate = float(primary_rate["rate"])
                as_of = primary_rate.get("date")
                forward_curve = get_synthetic_forward_curve(
                    pair=pair,
                    spot_rate=spot_rate,
                    as_of=as_of,
                )
                implied_volatility = get_synthetic_implied_volatility(
                    pair=pair,
                    as_of=as_of,
                )
                specialist_data = {
                    "source": "synthetic",
                    "provenance": (
                        "Deterministic AI Market Studio demo assumptions; "
                        "not live market quotes."
                    ),
                    "forward_curve": forward_curve,
                    "implied_volatility": implied_volatility,
                }
                synthetic_sources = synthetic_sources_for_playbook(selected_playbook)
                carry_metrics = build_fx_carry_metrics(
                    pair=pair,
                    spot_rate=spot_rate,
                    fred_rates=context.get("context", {}).get("fred", []),
                    forward_curve=forward_curve,
                    implied_volatility=implied_volatility,
                )
        playbook_sources = list(
            dict.fromkeys(
                list(selected_playbook.required_sources)
                + list(selected_playbook.optional_sources)
            )
        )
        missing_gap_sources = [
            source
            for source in selected_playbook.data_gap_sources
            if source not in synthetic_sources
        ]
        result = {
            "type": "market_briefing",
            "pairs": pairs,
            "playbook": {
                "id": selected_playbook.id,
                "display_name": selected_playbook.display_name,
                "required_sources": list(selected_playbook.required_sources),
                "optional_sources": list(selected_playbook.optional_sources),
                "output_sections": list(selected_playbook.output_sections),
                "research_only": selected_playbook.research_only,
            },
            "data_gaps": [
                {
                    "source": source,
                    "reason": "Specialist data is not available from current AI Market Studio connectors.",
                }
                for source in missing_gap_sources
            ],
            "source_grounding": {
                "available_sources": available_sources,
                "synthetic_sources": synthetic_sources,
                "requested_sources": playbook_sources,
                "missing_required_sources": [
                    source
                    for source in selected_playbook.required_sources
                    if source not in available_sources
                ],
                "missing_optional_sources": [
                    source
                    for source in selected_playbook.optional_sources
                    if source not in available_sources
                    and source not in synthetic_sources
                ],
            },
            "context": context,
            "analysis": analysis["analysis"],
            "briefing": {
                "summary": "Market briefing context collected and analyzed.",
                "focus": focus,
                "stance": "Research-only market briefing support; not live trading execution advice.",
            },
            "warnings": context.get("warnings", []),
        }
        if specialist_data is not None:
            result["specialist_data"] = specialist_data
        if carry_metrics is not None:
            result["carry_metrics"] = carry_metrics
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
