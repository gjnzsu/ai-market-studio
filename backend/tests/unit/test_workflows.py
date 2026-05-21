import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agent.workflows import (
    analyze_market_context,
    collect_market_context,
    generate_market_briefing,
)


@pytest.mark.asyncio
async def test_collect_market_context_returns_data_only():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }

    result = await collect_market_context(
        pairs=["EUR/USD"],
        sources=["rates"],
        connector=connector,
    )

    assert result["type"] == "market_context"
    assert result["context"]["rates"][0]["rate"] == 1.08
    assert "analysis" not in result
    assert "briefing" not in result


@pytest.mark.asyncio
async def test_analyze_market_context_returns_analysis_not_briefing():
    context = {
        "type": "market_context",
        "context": {
            "rates": [
                {"date": "2026-05-19", "rate": 1.07},
                {"date": "2026-05-20", "rate": 1.08},
            ]
        },
        "warnings": [],
    }

    result = await analyze_market_context(
        context=context,
        analysis_type="trend",
    )

    assert result["type"] == "market_analysis"
    assert "analysis" in result
    assert "briefing" not in result


@pytest.mark.asyncio
async def test_generate_market_briefing_coordinates_context_and_analysis():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }
    news_connector = MagicMock()
    news_connector.get_fx_news.return_value = []

    result = await generate_market_briefing(
        pairs=["EUR/USD"],
        connector=connector,
        news_connector=news_connector,
        include_research=False,
    )

    assert result["type"] == "market_briefing"
    assert "context" in result
    assert "analysis" in result
    assert "briefing" in result


@pytest.mark.asyncio
async def test_market_briefing_represents_optional_research_failure():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }
    rag = AsyncMock()
    rag.query_research.side_effect = Exception("RAG down")

    result = await generate_market_briefing(
        pairs=["EUR/USD"],
        connector=connector,
        include_news=False,
        include_fred=False,
        include_research=True,
        rag_connector=rag,
    )

    assert result["type"] == "market_briefing"
    assert any(w["source"] == "research" for w in result["warnings"])


@pytest.mark.asyncio
async def test_market_context_required_rate_failure_is_not_success():
    connector = AsyncMock()
    connector.get_exchange_rate.side_effect = Exception("rates down")

    with pytest.raises(Exception, match="rates down"):
        await collect_market_context(
            pairs=["EUR/USD"],
            sources=["rates"],
            connector=connector,
        )
