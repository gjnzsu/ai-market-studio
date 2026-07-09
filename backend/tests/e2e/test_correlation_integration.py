"""End-to-end integration test for economic relationship analysis through chat endpoint."""

from unittest.mock import AsyncMock, MagicMock

from backend.main import app
from backend.connectors.base import MarketDataConnector
from datetime import datetime, timedelta


def generate_mock_fx_data(start_date: str, days: int):
    """Generate mock FX data for testing."""
    start = datetime.fromisoformat(start_date)
    data = {}
    for i in range(days):
        date = (start + timedelta(days=i)).isoformat()
        rate = 1.08 - (0.0003 * i)  # Declining trend
        data[date] = {"USD": rate}
    return data


def make_tool_call_response(tool_name: str, arguments: str):
    """Create a mock OpenAI response with tool call."""
    tool_call = MagicMock()
    tool_call.id = "call_123"
    tool_call.type = "function"
    tool_call.function.name = tool_name
    tool_call.function.arguments = arguments

    msg = MagicMock()
    msg.content = None
    msg.tool_calls = [tool_call]
    msg.role = "assistant"

    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = "tool_calls"

    response = MagicMock()
    response.choices = [choice]
    return response


def make_text_response(content: str):
    """Create a mock OpenAI response with text content."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = None
    msg.role = "assistant"

    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = "stop"

    response = MagicMock()
    response.choices = [choice]
    return response


def test_correlation_integration_via_chat(app_client, monkeypatch):
    """Test correlation analysis through the chat endpoint."""
    monkeypatch.setattr("backend.router.settings.enable_agent_workflow_mode", True)

    # Setup mocks
    mock_market_connector = AsyncMock(spec=MarketDataConnector)

    start_date = "2024-01-25"
    days = 90

    # Mock FX data
    fx_data = generate_mock_fx_data(start_date, days)
    mock_market_connector.get_historical_rates.return_value = fx_data

    tool_call_response = make_tool_call_response(
        "analyze_market_context",
        '{"pairs": ["EUR/USD"], "analysis_type": "economic_relationship", "days": 90}'
    )
    text_response = make_text_response(
        "EUR/USD economic relationship analysis is complete with a declining 90-day trend."
    )

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create.side_effect = [
        tool_call_response,
        text_response
    ]

    monkeypatch.setattr("backend.agent.agent.AsyncOpenAI", lambda **kwargs: mock_openai)

    app.state.connector = mock_market_connector

    response = app_client.post(
        "/api/chat",
        json={
            "message": "How does EUR/USD correlate with Fed rate changes over the last 90 days?",
            "history": []
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert "reply" in data
    assert "EUR/USD" in data["reply"]
    assert "analysis" in data["reply"].lower()
    assert data.get("tool_used") == "analyze_market_context"
    assert data.get("data") is not None
    assert data["data"]["type"] == "market_analysis"
    assert data["data"]["analysis"]["analysis_type"] == "economic_relationship"
    assert data["data"]["analysis"]["pairs"][0]["pair"] == "EUR/USD"


def test_correlation_integration_multiple_indicators(app_client, monkeypatch):
    """Test correlation analysis with multiple indicators."""
    monkeypatch.setattr("backend.router.settings.enable_agent_workflow_mode", True)

    mock_market_connector = AsyncMock(spec=MarketDataConnector)

    start_date = "2024-01-25"
    days = 90

    fx_data = generate_mock_fx_data(start_date, days)
    mock_market_connector.get_historical_rates.return_value = fx_data

    tool_call_response = make_tool_call_response(
        "analyze_market_context",
        '{"pairs": ["EUR/USD"], "analysis_type": "economic_relationship", "days": 90}'
    )
    text_response = make_text_response(
        "Analysis compares EUR/USD with Fed rates and 10-Year Treasury context."
    )

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create.side_effect = [
        tool_call_response,
        text_response
    ]

    monkeypatch.setattr("backend.agent.agent.AsyncOpenAI", lambda **kwargs: mock_openai)

    app.state.connector = mock_market_connector

    response = app_client.post(
        "/api/chat",
        json={
            "message": "Correlate EUR/USD with Fed rates and 10Y Treasury",
            "history": []
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert data["tool_used"] == "analyze_market_context"
    assert data["data"]["type"] == "market_analysis"
    assert data["data"]["analysis"]["pairs"][0]["pair"] == "EUR/USD"
