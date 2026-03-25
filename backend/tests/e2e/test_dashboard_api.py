import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.connectors.mock_connector import MockConnector
from backend.connectors.base import RateFetchError


@pytest.fixture
def client():
    app = create_app()
    app.state.connector = MockConnector()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# POST /api/rates/historical
# ---------------------------------------------------------------------------

def test_historical_rates_endpoint_happy_path(client):
    """POST /api/rates/historical returns 200 with correct series length."""
    resp = client.post("/api/rates/historical", json={
        "base": "USD",
        "targets": ["EUR", "GBP"],
        "start_date": "2025-01-01",
        "end_date": "2025-01-05",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["base"] == "USD"
    assert len(data["series"]) == 5
    assert data["cached"] is False
    assert data["series"][0]["date"] == "2025-01-01"
    assert "EUR" in data["series"][0]["rates"]
    assert "GBP" in data["series"][0]["rates"]


def test_historical_rates_endpoint_cache_hit(client):
    """Second identical POST returns cached=True."""
    payload = {
        "base": "USD",
        "targets": ["EUR"],
        "start_date": "2025-02-01",
        "end_date": "2025-02-03",
    }
    resp1 = client.post("/api/rates/historical", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["cached"] is False

    resp2 = client.post("/api/rates/historical", json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["cached"] is True


def test_historical_rates_endpoint_422_on_bad_request(client):
    """Missing base field returns HTTP 422."""
    resp = client.post("/api/rates/historical", json={
        "targets": ["EUR"],
        "start_date": "2025-01-01",
        "end_date": "2025-01-05",
    })
    assert resp.status_code == 422


def test_historical_rates_endpoint_422_on_date_range_too_large(client):
    """Date range >= 7 days returns HTTP 422."""
    resp = client.post("/api/rates/historical", json={
        "base": "USD",
        "targets": ["EUR"],
        "start_date": "2025-01-01",
        "end_date": "2025-01-08",
    })
    assert resp.status_code == 422


def test_historical_rates_endpoint_502_on_connector_error(client, monkeypatch):
    """ConnectorError propagates as HTTP 502."""
    async def failing_get_historical(*args, **kwargs):
        raise RateFetchError("Simulated connector failure")
    monkeypatch.setattr(
        "backend.router.rate_cache.get", lambda *a, **kw: None
    )
    client.app.state.connector.get_historical_rates = failing_get_historical
    resp = client.post("/api/rates/historical", json={
        "base": "USD",
        "targets": ["EUR"],
        "start_date": "2025-03-01",
        "end_date": "2025-03-03",
    })
    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# POST /api/dashboard
# ---------------------------------------------------------------------------

def _panel(panel_id="p1", panel_type="line_trend", base="USD",
           targets=None, start="2025-01-01", end="2025-01-05"):
    return {
        "panel_id": panel_id,
        "panel_type": panel_type,
        "base": base,
        "targets": targets or ["EUR"],
        "start_date": start,
        "end_date": end,
    }


def test_dashboard_endpoint_happy_path(client):
    """POST /api/dashboard with 2 panels returns 2 panel results."""
    resp = client.post("/api/dashboard", json={
        "dashboard_id": "dash-test",
        "dashboard_type": "trend",
        "panels": [
            _panel("p1", targets=["EUR"]),
            _panel("p2", panel_type="bar_comparison", targets=["GBP"]),
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["dashboard_id"] == "dash-test"
    assert len(data["panels"]) == 2
    panel_ids = [p["panel_id"] for p in data["panels"]]
    assert "p1" in panel_ids
    assert "p2" in panel_ids


def test_dashboard_endpoint_panel_data_has_series(client):
    """Each panel result contains a data.series list."""
    resp = client.post("/api/dashboard", json={
        "dashboard_id": "dash-2",
        "dashboard_type": "mixed",
        "panels": [_panel("p1", targets=["EUR", "GBP"])],
    })
    assert resp.status_code == 200
    panel = resp.json()["panels"][0]
    assert "data" in panel
    assert "series" in panel["data"]
    assert len(panel["data"]["series"]) == 5


def test_dashboard_endpoint_502_on_connector_error(client, monkeypatch):
    """ConnectorError from mock propagates as HTTP 502."""
    async def failing_get_historical(*args, **kwargs):
        raise RateFetchError("Simulated connector failure")
    monkeypatch.setattr(
        "backend.router.rate_cache.get", lambda *a, **kw: None
    )
    client.app.state.connector.get_historical_rates = failing_get_historical
    resp = client.post("/api/dashboard", json={
        "dashboard_id": "dash-err",
        "dashboard_type": "trend",
        "panels": [_panel("p1", start="2025-04-01", end="2025-04-03")],
    })
    assert resp.status_code == 502


def test_dashboard_endpoint_422_on_empty_panels(client):
    """Empty panels list returns 422."""
    resp = client.post("/api/dashboard", json={
        "dashboard_id": "dash-bad",
        "dashboard_type": "trend",
        "panels": [],
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Regression: Feature 01 chat endpoint unaffected
# ---------------------------------------------------------------------------

def test_existing_chat_endpoint_still_works(client, monkeypatch):
    """POST /api/chat unaffected by dashboard additions."""
    from unittest.mock import AsyncMock, MagicMock

    msg = MagicMock()
    msg.content = "EUR/USD is 1.08"
    msg.tool_calls = None
    msg.model_dump.return_value = {"role": "assistant", "content": "EUR/USD is 1.08", "tool_calls": []}
    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = "stop"
    response = MagicMock()
    response.choices = [choice]

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(return_value=response)
    monkeypatch.setattr("backend.agent.agent.AsyncOpenAI", lambda **kwargs: mock_openai)

    resp = client.post("/api/chat", json={"message": "What is EUR/USD?"})
    assert resp.status_code == 200
    assert "reply" in resp.json()
