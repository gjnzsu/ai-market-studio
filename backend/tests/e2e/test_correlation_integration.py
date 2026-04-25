"""End-to-end integration test for correlation analysis through chat endpoint."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from backend.main import app
from backend.connectors.base import MarketDataConnector
from backend.connectors.fred_connector import HistoricalRatesData, HistoricalObservation
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


def generate_mock_fred_data(start_date: str, days: int):
    """Generate mock FRED data for testing."""
    start = datetime.fromisoformat(start_date)
    observations = []
    for i in range(days):
        date = (start + timedelta(days=i)).isoformat()
        value = 5.25 + (0.008 * i)  # Rising trend
        observations.append(HistoricalObservation(date=date, value=value))

    return HistoricalRatesData(
        series_id="DFF",
        series_name="Effective Federal Funds Rate",
        start_date=start_date,
        end_date=(start + timedelta(days=days-1)).isoformat(),
        observations=observations,
        count=len(observations),
        source="FRED"
    )


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

    # Setup mocks
    mock_market_connector = AsyncMock(spec=MarketDataConnector)

    start_date = "2024-01-25"
    days = 90

    # Mock FX data
    fx_data = generate_mock_fx_data(start_date, days)
    mock_market_connector.get_historical_rates.return_value = fx_data

    # Mock FRED connector
    with patch("backend.connectors.correlation_connector.FREDConnector") as mock_fred_class:
        mock_fred_instance = AsyncMock()
        fred_data = generate_mock_fred_data(start_date, days)
        mock_fred_instance.get_historical_rates.return_value = fred_data
        mock_fred_class.return_value = mock_fred_instance

        # Mock OpenAI responses
        tool_call_response = make_tool_call_response(
            "analyze_fx_economic_correlation",
            '{"pair": "EUR/USD", "indicators": ["DFF"], "days": 90}'
        )
        text_response = make_text_response(
            "Over the past 90 days, EUR/USD declined 2.78% while the Federal Funds Rate rose 75 basis points. "
            "The directional alignment is 78.5%, indicating a strong inverse correlation."
        )

        mock_openai = AsyncMock()
        mock_openai.chat.completions.create.side_effect = [
            tool_call_response,
            text_response
        ]

        monkeypatch.setattr("backend.agent.agent.AsyncOpenAI", lambda **kwargs: mock_openai)

        # Patch connector in app
        app.state.connector = mock_market_connector

        # Make request
        response = app_client.post(
            "/api/chat",
            json={
                "message": "How does EUR/USD correlate with Fed rate changes over the last 90 days?",
                "history": []
            }
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert "reply" in data
        assert "EUR/USD" in data["reply"]
        assert "correlation" in data["reply"].lower()

        # Verify tool was used
        assert data.get("tool_used") == "analyze_fx_economic_correlation"

        # Verify data payload
        assert data.get("data") is not None
        assert data["data"]["type"] == "economic_correlation"
        assert "pair" in data["data"]["data"]
        assert data["data"]["data"]["pair"] == "EUR/USD"
        assert "directional_alignment" in data["data"]["data"]
        assert "trend_summary" in data["data"]["data"]


def test_correlation_integration_multiple_indicators(app_client, monkeypatch):
    """Test correlation analysis with multiple indicators."""

    mock_market_connector = AsyncMock(spec=MarketDataConnector)

    start_date = "2024-01-25"
    days = 90

    fx_data = generate_mock_fx_data(start_date, days)
    mock_market_connector.get_historical_rates.return_value = fx_data

    # Mock FRED connector with multiple series
    with patch("backend.connectors.correlation_connector.FREDConnector") as mock_fred_class:
        mock_fred_instance = AsyncMock()

        async def mock_get_historical(series_id, start_date, end_date):
            data = generate_mock_fred_data(start_date, days)
            if series_id == "DGS10":
                data.series_id = "DGS10"
                data.series_name = "10-Year Treasury"
            return data

        mock_fred_instance.get_historical_rates.side_effect = mock_get_historical
        mock_fred_class.return_value = mock_fred_instance

        # Mock OpenAI responses
        tool_call_response = make_tool_call_response(
            "analyze_fx_economic_correlation",
            '{"pair": "EUR/USD", "indicators": ["DFF", "DGS10"], "days": 90}'
        )
        text_response = make_text_response(
            "Analysis shows correlation with both Fed Funds Rate and 10-Year Treasury."
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

        # Verify multiple indicators in response
        assert len(data["data"]["data"]["indicators"]) == 2
        assert data["data"]["data"]["indicators"][0]["series_id"] in ["DFF", "DGS10"]
        assert data["data"]["data"]["indicators"][1]["series_id"] in ["DFF", "DGS10"]
