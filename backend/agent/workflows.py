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
from backend.connectors.base import MarketDataConnector
from backend.connectors.news_connector import NewsConnectorBase

logger = logging.getLogger(__name__)


def _split_pair(pair: str) -> tuple[str, str]:
    normalized = pair.upper().replace("-", "/")
    if "/" not in normalized and len(normalized) == 6 and normalized.isalpha():
        return normalized[:3], normalized[3:]
    parts = normalized.split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid currency pair: {pair}")
    return parts[0], parts[1]


def _format_pair(pair: str) -> str:
    base, target = _split_pair(pair)
    return f"{base}/{target}"


def _pair_from_rate(rate: dict[str, Any], fallback: Optional[str] = None) -> str:
    base = rate.get("base")
    target = rate.get("target")
    if base and target:
        return f"{str(base).upper()}/{str(target).upper()}"
    if fallback:
        return _format_pair(fallback)
    return "UNKNOWN/UNKNOWN"


def _normalize_pairs(
    pairs: Optional[list[str]], market_context: dict[str, Any]
) -> list[str]:
    if pairs:
        return [_format_pair(pair) for pair in pairs]

    metadata_pairs = market_context.get("metadata", {}).get("pairs")
    if metadata_pairs:
        return [_format_pair(pair) for pair in metadata_pairs]

    rates = market_context.get("context", {}).get("rates", [])
    normalized = []
    for rate in rates:
        pair = _pair_from_rate(rate)
        if pair != "UNKNOWN/UNKNOWN" and pair not in normalized:
            normalized.append(pair)
    return normalized


def _extract_research_sources(research: Any) -> list[str]:
    if not isinstance(research, dict):
        return []

    raw_sources = research.get("sources") or research.get("documents") or []
    names = []
    for source in raw_sources:
        if isinstance(source, dict):
            name = (
                source.get("title")
                or source.get("name")
                or source.get("document_id")
                or source.get("id")
            )
        else:
            name = str(source)
        if name:
            names.append(str(name))
    return names


def _extract_rate_sources(rates: list[dict[str, Any]]) -> list[str]:
    sources = []
    for rate in rates:
        source = rate.get("source")
        if source and source not in sources:
            sources.append(str(source))
    return sources


def _rate_value(rate: dict[str, Any]) -> Optional[float]:
    try:
        return float(rate["rate"])
    except (KeyError, TypeError, ValueError):
        return None


def _build_pair_summary(pair: str, rates: list[dict[str, Any]]) -> dict[str, Any]:
    values = [value for value in (_rate_value(rate) for rate in rates) if value is not None]
    latest_rate = values[-1] if values else None
    first_rate = values[0] if values else None
    change = None
    direction = "insufficient_data"
    if len(values) >= 2:
        change = latest_rate - first_rate
        if change > 0:
            direction = "higher"
        elif change < 0:
            direction = "lower"
        else:
            direction = "flat"

    return {
        "pair": pair,
        "latest_rate": latest_rate,
        "observation_count": len(values),
        "direction": direction,
        "change": change,
    }


def build_fx_analysis(
    market_context: dict[str, Any],
    pairs: Optional[list[str]] = None,
    horizon: Optional[str] = None,
    focus: Optional[str] = None,
    analysis_type: str = "fx_analysis",
) -> dict[str, Any]:
    normalized_pairs = _normalize_pairs(pairs, market_context)
    primary_pair = normalized_pairs[0] if normalized_pairs else "UNKNOWN/UNKNOWN"
    context_body = market_context.get("context", {})
    rates = context_body.get("rates", [])

    rates_by_pair: dict[str, list[dict[str, Any]]] = {pair: [] for pair in normalized_pairs}
    for index, rate in enumerate(rates):
        fallback = normalized_pairs[index] if index < len(normalized_pairs) else primary_pair
        pair = _pair_from_rate(rate, fallback=fallback)
        rates_by_pair.setdefault(pair, []).append(rate)
        if pair not in normalized_pairs:
            normalized_pairs.append(pair)

    primary_rates = rates_by_pair.get(primary_pair, [])
    primary_summary = _build_pair_summary(primary_pair, primary_rates)
    rate_sources = _extract_rate_sources(rates)
    pair_summaries = [
        _build_pair_summary(pair, rates_by_pair.get(pair, []))
        for pair in normalized_pairs
    ]

    latest_change = primary_summary["change"]
    observations = [
        value
        for value in (_rate_value(rate) for rate in primary_rates)
        if value is not None
    ]
    if len(observations) >= 2:
        step_changes = [
            abs(observations[index] - observations[index - 1])
            for index in range(1, len(observations))
        ]
        average_absolute_change = sum(step_changes) / len(step_changes)
        volatility_state = "observable"
    else:
        average_absolute_change = None
        volatility_state = "insufficient_history"

    available_sources = list(context_body.keys())
    warnings = market_context.get("warnings", [])
    warning_sources = [warning.get("source") for warning in warnings if warning.get("source")]
    data_gaps = [
        {"source": source, "reason": "Optional source unavailable for this analysis."}
        for source in warning_sources
    ]
    if len(primary_rates) < 2:
        data_gaps.append(
            {
                "source": "history",
                "reason": "At least two rate observations are needed for trend and volatility depth.",
            }
        )

    requested_sources = market_context.get("metadata", {}).get("sources", ["rates"])
    for source in requested_sources:
        if source not in available_sources and source not in warning_sources:
            data_gaps.append(
                {"source": source, "reason": "Requested source was not present in context."}
            )

    research_sources = _extract_research_sources(context_body.get("research"))
    driver_items = []
    if "news" in context_body:
        driver_items.append({"source": "news", "summary": "News context is available."})
    if "fred" in context_body:
        driver_items.append({"source": "fred", "summary": "Macro rate context is available."})
    if "research" in context_body:
        driver_items.append(
            {
                "source": "research",
                "summary": "Research context is available.",
                "sources": research_sources,
            }
        )

    score = 0.35
    if primary_rates:
        score += 0.25
    if len(primary_rates) >= 2:
        score += 0.2
    if driver_items:
        score += 0.15
    if not data_gaps:
        score += 0.05
    elif len(data_gaps) >= 2:
        score = min(score, 0.7)
    score = min(round(score, 2), 1.0)
    label = "high" if score >= 0.75 else "medium" if score >= 0.5 else "low"

    result = {
        "type": "fx_analysis",
        "analysis_type": analysis_type,
        "pair": primary_pair,
        "pairs": normalized_pairs,
        "pair_summaries": pair_summaries,
        "horizon": horizon or "1w",
        "focus": focus,
        "market_context_summary": {
            "primary_pair": primary_pair,
            "requested_pairs": normalized_pairs,
            "available_sources": available_sources,
            "rate_sources": rate_sources,
            "latest_rate": primary_summary["latest_rate"],
            "observation_count": primary_summary["observation_count"],
        },
        "sections": {
            "trend": {
                "direction": primary_summary["direction"],
                "change": latest_change,
                "basis": "available rate observations",
            },
            "momentum": {
                "latest_change": latest_change,
                "state": (
                    "observable"
                    if latest_change is not None
                    else "insufficient_history"
                ),
            },
            "volatility": {
                "state": volatility_state,
                "average_absolute_change": average_absolute_change,
                "observation_count": len(observations),
            },
            "drivers": driver_items,
            "watch_items": [
                "Upcoming macro data and central bank communication",
                "Fresh spot and historical rate observations",
            ],
            "limitations": [
                gap["reason"]
                for gap in data_gaps
            ],
        },
        "scenarios": {
            "bull": "Research scenario where the base currency strengthens versus the quote currency.",
            "base": "Research scenario where recent rate behavior remains broadly consistent.",
            "bear": "Research scenario where the base currency weakens versus the quote currency.",
        },
        "data_gaps": data_gaps,
        "source_grounding": {
            "available_sources": available_sources,
            "rate_sources": rate_sources,
            "requested_sources": requested_sources,
            "research_sources": research_sources,
        },
        "confidence": {"score": score, "label": label},
        "research_only": True,
        "framing": "Research-only FX analysis support; not live trading execution advice.",
        "warnings": warnings,
        "context": market_context,
    }
    return result


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
        if days and days > 1:
            end_date = date_type.today()
            start_date = end_date - timedelta(days=days - 1)
            for pair in pairs or []:
                base, target = _split_pair(pair)
                history = await connector.get_historical_rates(
                    base=base,
                    targets=[target],
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                )
                for observed_date, targets in history.items():
                    if target in targets:
                        rate_results.append(
                            {
                                "base": base,
                                "target": target,
                                "rate": targets[target],
                                "date": observed_date,
                            }
                        )
        else:
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
    horizon: Optional[str] = None,
    focus: Optional[str] = None,
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

    if analysis_type == "fx_analysis":
        return build_fx_analysis(
            market_context=market_context,
            pairs=pairs,
            horizon=horizon,
            focus=focus,
            analysis_type=analysis_type,
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
