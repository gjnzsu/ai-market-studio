import pytest
from pydantic import ValidationError
from backend.models import (
    ChatRequest, ChatResponse, Message,
    HistoricalRatesRequest, DailyRates, HistoricalRatesResponse,
    DashboardPanelConfig, DashboardConfig,
)


def test_chat_request_valid():
    req = ChatRequest(message="What is EUR/USD?")
    assert req.message == "What is EUR/USD?"
    assert req.history == []


def test_chat_request_with_history():
    req = ChatRequest(
        message="And GBP?",
        history=[{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}],
    )
    assert len(req.history) == 2


def test_chat_request_empty_message_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(message="")


def test_chat_request_whitespace_message_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(message="   ")


def test_chat_response_valid():
    resp = ChatResponse(reply="EUR/USD is 1.08", data={"rate": 1.08}, tool_used="get_exchange_rate")
    assert resp.reply == "EUR/USD is 1.08"


def test_chat_response_minimal():
    resp = ChatResponse(reply="Hello")
    assert resp.data is None
    assert resp.tool_used is None


# ---------------------------------------------------------------------------
# Feature 02 — HistoricalRatesRequest validation
# ---------------------------------------------------------------------------

def test_historical_rates_request_valid():
    req = HistoricalRatesRequest(
        base="usd",
        targets=["eur", "gbp"],
        start_date="2025-01-01",
        end_date="2025-01-05",
    )
    assert req.base == "USD"
    assert req.targets == ["EUR", "GBP"]


def test_historical_rates_request_uppercases_fields():
    """base and targets are uppercased by validator."""
    req = HistoricalRatesRequest(
        base="eur",
        targets=["usd", "gbp"],
        start_date="2025-01-01",
        end_date="2025-01-05",
    )
    assert req.base == "EUR"
    assert all(t == t.upper() for t in req.targets)


def test_historical_rates_request_rejects_bad_date_format():
    """Non-ISO date string raises ValidationError."""
    with pytest.raises(ValidationError):
        HistoricalRatesRequest(
            base="USD",
            targets=["EUR"],
            start_date="01/01/2025",
            end_date="2025-01-05",
        )


def test_historical_rates_request_rejects_range_too_large():
    """Date range >= max_historical_days (7) raises ValidationError."""
    with pytest.raises(ValidationError):
        HistoricalRatesRequest(
            base="USD",
            targets=["EUR"],
            start_date="2025-01-01",
            end_date="2025-01-08",  # 7 days diff >= limit
        )


def test_historical_rates_request_accepts_max_minus_one_days():
    """Date range of 6 days (diff=6, < 7) is accepted."""
    req = HistoricalRatesRequest(
        base="USD",
        targets=["EUR"],
        start_date="2025-01-01",
        end_date="2025-01-07",  # 6 days diff
    )
    assert req.start_date == "2025-01-01"


# ---------------------------------------------------------------------------
# Feature 02 — DashboardConfig validation
# ---------------------------------------------------------------------------

def _make_panel(panel_id="p1"):
    return {
        "panel_id": panel_id,
        "panel_type": "line_trend",
        "base": "USD",
        "targets": ["EUR"],
        "start_date": "2025-01-01",
        "end_date": "2025-01-05",
    }


def test_dashboard_config_valid():
    config = DashboardConfig(
        dashboard_id="dash-1",
        dashboard_type="trend",
        panels=[_make_panel()],
    )
    assert len(config.panels) == 1


def test_dashboard_config_rejects_zero_panels():
    """Empty panels list raises ValidationError."""
    with pytest.raises(ValidationError):
        DashboardConfig(
            dashboard_id="dash-1",
            dashboard_type="trend",
            panels=[],
        )


def test_dashboard_config_rejects_too_many_panels():
    """10 panels raises ValidationError (max=9)."""
    with pytest.raises(ValidationError):
        DashboardConfig(
            dashboard_id="dash-1",
            dashboard_type="trend",
            panels=[_make_panel(f"p{i}") for i in range(10)],
        )


def test_dashboard_config_accepts_nine_panels():
    """Exactly 9 panels is valid."""
    config = DashboardConfig(
        dashboard_id="dash-1",
        dashboard_type="mixed",
        panels=[_make_panel(f"p{i}") for i in range(9)],
    )
    assert len(config.panels) == 9


def test_dashboard_panel_config_invalid_type():
    """Unknown panel_type raises ValidationError."""
    with pytest.raises(ValidationError):
        DashboardPanelConfig(
            panel_id="p1",
            panel_type="unknown_type",
            base="USD",
            targets=["EUR"],
            start_date="2025-01-01",
            end_date="2025-01-05",
        )
