# backend/tests/unit/test_data_collector.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.agents.data_collector import collect_market_data


@pytest.mark.asyncio
async def test_collect_rates_data():
    """Test collecting FX rate data."""
    mock_connector = AsyncMock()
    mock_connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.0850,
        "date": "2026-04-26",
        "source": "mock"
    }

    result = await collect_market_data(
        data_type="rates",
        pairs=["EUR/USD"],
        connector=mock_connector
    )

    assert result["data_type"] == "rates"
    assert result["source"] == "mock"
    assert len(result["data"]) == 1
    assert result["data"][0]["rate"] == 1.0850
    assert "metadata" in result


@pytest.mark.asyncio
async def test_collect_news_data():
    """Test collecting news data."""
    mock_connector = MagicMock()
    mock_connector.get_fx_news.return_value = [
        {
            "title": "Fed holds rates steady",
            "summary": "The Federal Reserve kept rates unchanged.",
            "source": "Mock Financial Times",
            "published": "2026-04-26T14:00:00+00:00",
            "url": "https://example.com/news/fed"
        },
        {
            "title": "EUR/USD climbs on ECB news",
            "summary": "Euro strengthened against dollar.",
            "source": "Mock FX Street",
            "published": "2026-04-26T10:30:00+00:00",
            "url": "https://example.com/news/eurusd"
        }
    ]

    result = await collect_market_data(
        data_type="news",
        news_connector=mock_connector,
        query="EUR"
    )

    assert result["data_type"] == "news"
    assert result["source"] == "Mock Financial Times"
    assert len(result["data"]) == 2
    assert result["data"][0]["title"] == "Fed holds rates steady"
    assert result["metadata"]["count"] == 2
    assert result["metadata"]["query"] == "EUR"
    mock_connector.get_fx_news.assert_called_once_with(query="EUR", max_items=5)


@pytest.mark.asyncio
async def test_collect_fred_data():
    """Test collecting FRED interest rate data."""
    mock_connector = AsyncMock()
    mock_rate_data = MagicMock()
    mock_rate_data.model_dump.return_value = {
        "series_id": "DFF",
        "series_name": "Effective Federal Funds Rate",
        "date": "2026-04-25",
        "value": 3.64,
        "unit": "percent",
        "source": "FRED"
    }
    mock_connector.get_current_rate.return_value = mock_rate_data

    result = await collect_market_data(
        data_type="fred",
        fred_connector=mock_connector,
        series_id="DFF"
    )

    assert result["data_type"] == "fred"
    assert result["source"] == "FRED"
    assert result["data"]["series_id"] == "DFF"
    assert result["data"]["value"] == 3.64
    assert result["metadata"]["series_id"] == "DFF"
    mock_connector.get_current_rate.assert_called_once_with(series_id="DFF", date=None)


@pytest.mark.asyncio
async def test_collect_rag_data():
    """Test collecting RAG research data."""
    mock_connector = AsyncMock()
    mock_connector.query_research.return_value = {
        "type": "rag",
        "answer": "The Federal Reserve's monetary policy affects currency markets...",
        "sources": [
            {"name": "Fed Policy Report 2026"},
            {"name": "Currency Market Analysis"}
        ]
    }

    result = await collect_market_data(
        data_type="rag",
        rag_connector=mock_connector,
        query="How does Fed policy affect FX markets?"
    )

    assert result["data_type"] == "rag"
    assert result["source"] == "RAG"
    assert "answer" in result["data"]
    assert len(result["data"]["sources"]) == 2
    assert result["metadata"]["sources_count"] == 2
    assert result["metadata"]["query"] == "How does Fed policy affect FX markets?"
    mock_connector.query_research.assert_called_once_with(
        question="How does Fed policy affect FX markets?"
    )


@pytest.mark.asyncio
async def test_collect_invalid_data_type():
    """Test error handling for invalid data_type."""
    mock_connector = AsyncMock()

    with pytest.raises(ValueError) as exc_info:
        await collect_market_data(
            data_type="invalid_type",
            connector=mock_connector
        )

    assert "Invalid data_type: invalid_type" in str(exc_info.value)
    assert "Must be one of: rates, news, fred, rag" in str(exc_info.value)

