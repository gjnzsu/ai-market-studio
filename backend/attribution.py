"""Cost attribution helpers for AI Market Studio chat workflows."""

from __future__ import annotations

import re
import uuid
from typing import Any

from backend.config import settings
from backend.models import ChatClientContext

DEFAULT_APPLICATION_ID = "ai-market-studio"
DEFAULT_PROJECT_ID = "fx-market-insight"
DEFAULT_TEAM_ID = "markets"
DEFAULT_USE_CASE = "fx-data-query"
DEFAULT_FEATURE = "query-result-generation"

_SAFE_LABEL_RE = re.compile(r"[^a-zA-Z0-9_.:-]+")
_DASHBOARD_INTENT_RE = re.compile(
    r"\b(chart|dashboard|visuali[sz]e|plot|trend|show|display)\b",
    re.IGNORECASE,
)


def ensure_request_id(context: ChatClientContext | None) -> str:
    if context and context.request_id:
        return context.request_id
    return str(uuid.uuid4())


def _safe_label(value: str | None, default: str) -> str:
    raw = (value or default).strip() or default
    return _SAFE_LABEL_RE.sub("-", raw)[:80]


def classify_use_case(
    *,
    message: str,
    tool_used: str | None,
    data: Any,
    context: ChatClientContext | None,
) -> tuple[str, str]:
    """Classify chat executions into the MVP attribution dimensions."""
    if context and context.use_case and context.feature:
        return context.use_case, context.feature

    result_type = data.get("type") if isinstance(data, dict) else None
    if tool_used == "generate_market_briefing" or result_type == "market_briefing":
        return "fx-advisory-report", "advisory-report-generation"

    if result_type == "dashboard" or _DASHBOARD_INTENT_RE.search(message):
        return "chat-dashboard-generation", "dashboard-generation"

    if tool_used in {"collect_market_context", "analyze_market_context"} or result_type in {
        "market_context",
        "market_analysis",
    }:
        return "fx-data-query", "query-result-generation"

    return DEFAULT_USE_CASE, DEFAULT_FEATURE


def attribution_headers(
    *,
    context: ChatClientContext | None,
    request_id: str,
    use_case: str | None = None,
    feature: str | None = None,
) -> dict[str, str]:
    """Headers safe to forward through Kong and ai-gateway-service."""
    application_id = context.application_id if context else None
    project_id = context.project_id if context else None
    team_id = context.team_id if context else None
    return {
        "X-Request-ID": request_id,
        "X-Consumer-Service": DEFAULT_APPLICATION_ID,
        "X-AI-Application-ID": _safe_label(application_id, DEFAULT_APPLICATION_ID),
        "X-AI-Project-ID": _safe_label(project_id, DEFAULT_PROJECT_ID),
        "X-AI-Team-ID": _safe_label(team_id, DEFAULT_TEAM_ID),
        "X-AI-Use-Case": _safe_label(use_case, DEFAULT_USE_CASE),
        "X-AI-Feature": _safe_label(feature, DEFAULT_FEATURE),
    }


def business_metric_labels(
    *,
    context: ChatClientContext | None,
    use_case: str,
    feature: str,
    tool_used: str | None,
    status: str,
) -> dict[str, str]:
    """Return low-cardinality labels for Prometheus business attribution."""
    return {
        "application": _safe_label(
            context.application_id if context else None,
            DEFAULT_APPLICATION_ID,
        ),
        "project": _safe_label(context.project_id if context else None, DEFAULT_PROJECT_ID),
        "team": _safe_label(context.team_id if context else None, DEFAULT_TEAM_ID),
        "use_case": _safe_label(use_case, DEFAULT_USE_CASE),
        "feature": _safe_label(feature, DEFAULT_FEATURE),
        "model": _safe_label(settings.openai_model, "unknown"),
        "status": _safe_label(status, "success"),
        "tool_used": _safe_label(tool_used, "none"),
    }
