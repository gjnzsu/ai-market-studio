"""Unit test for generate_market_insight with RAG integration."""
import pytest
from unittest.mock import AsyncMock, patch
from backend.agent.tools import dispatch_tool


@pytest.mark.asyncio
async def test_generate_market_insight_includes_research():
    """Test that market insight includes research reports."""
    # Mock connectors
    mock_connector = AsyncMock()
    mock_connector.get_exchange_rates.return_value = [
        {"base": "USD", "target": "EUR", "rate": 0.9217, "date": "2026-05-01", "source": "mock"}
    ]

    mock_news = AsyncMock()
    mock_news.get_fx_news.return_value = [
        {"title": "ECB holds rates", "summary": "...", "source": "Reuters", "published": "2026-05-01", "url": "http://example.com"}
    ]

    mock_rag = AsyncMock()
    mock_rag.query_research = AsyncMock(return_value={
        "type": "rag",
        "sources": [
            {"name": "Monthly FX Outlook.pdf", "excerpt": "EUR/USD expected to rise...", "document_id": "1", "source_type": "pdf", "title": "Monthly FX Outlook.pdf", "document_type": "general", "score": 0.9},
            {"name": "Daily Snapshot.pdf", "excerpt": "EUR strength continues...", "document_id": "2", "source_type": "pdf", "title": "Daily Snapshot.pdf", "document_type": "general", "score": 0.8}
        ]
    })

    # Call function
    result = await dispatch_tool(
        tool_name="generate_market_insight",
        tool_args={"pairs": ["EUR/USD"], "include_research": True},
        connector=mock_connector,
        news_connector=mock_news,
        rag_connector=mock_rag
    )

    # Verify structure
    assert result["type"] == "insight"
    assert "rates" in result
    assert "news" in result
    assert "research" in result
    assert len(result["research"]) == 2
    assert result["research"][0]["name"] == "Monthly FX Outlook.pdf"

    # Verify RAG was called with correct query
    mock_rag.query_research.assert_called_once()
    call_args = mock_rag.query_research.call_args
    assert "EUR" in call_args.kwargs["question"]
    assert "USD" in call_args.kwargs["question"]
    assert call_args.kwargs["document_type"] == "research_report"


@pytest.mark.asyncio
async def test_generate_market_insight_without_research():
    """Test that research can be disabled."""
    mock_connector = AsyncMock()
    mock_connector.get_exchange_rates.return_value = [
        {"base": "USD", "target": "EUR", "rate": 0.9217, "date": "2026-05-01", "source": "mock"}
    ]
    mock_news = AsyncMock()
    mock_news.get_fx_news.return_value = []
    mock_rag = AsyncMock()

    result = await dispatch_tool(
        tool_name="generate_market_insight",
        tool_args={"pairs": ["EUR/USD"], "include_research": False},
        connector=mock_connector,
        news_connector=mock_news,
        rag_connector=mock_rag
    )

    assert result["research"] == []
    mock_rag.query_research.assert_not_called()


@pytest.mark.asyncio
async def test_generate_market_insight_rag_failure_graceful():
    """Test that RAG failure doesn't break market insight."""
    mock_connector = AsyncMock()
    mock_connector.get_exchange_rates.return_value = [
        {"base": "USD", "target": "EUR", "rate": 0.9217, "date": "2026-05-01", "source": "mock"}
    ]
    mock_news = AsyncMock()
    mock_news.get_fx_news.return_value = []

    # Create a mock that raises exception when query_research is awaited
    async def raise_exception(*args, **kwargs):
        raise Exception("RAG service down")

    mock_rag = AsyncMock()
    mock_rag.query_research = raise_exception

    # Should not raise exception
    result = await dispatch_tool(
        tool_name="generate_market_insight",
        tool_args={"pairs": ["EUR/USD"], "include_research": True},
        connector=mock_connector,
        news_connector=mock_news,
        rag_connector=mock_rag
    )

    # Should still return rates and news
    assert result["type"] == "insight"
    assert "rates" in result
    assert result["research"] == []  # Empty due to failure
