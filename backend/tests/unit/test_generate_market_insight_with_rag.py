import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agent.tools import AgentError, dispatch_tool


@pytest.mark.asyncio
async def test_generate_market_briefing_includes_research_when_available():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }
    news = MagicMock()
    news.get_fx_news.return_value = []
    rag = AsyncMock()
    rag.query_research = AsyncMock(
        return_value={
            "type": "rag",
            "answer": "EUR/USD outlook is constructive.",
            "sources": [{"name": "Monthly FX Outlook.pdf"}],
        }
    )

    result = await dispatch_tool(
        "generate_market_briefing",
        {"pairs": ["EUR/USD"], "include_research": True},
        connector,
        news_connector=news,
        rag_connector=rag,
    )

    assert result["type"] == "market_briefing"
    assert "research" in result["context"]["context"]
    rag.query_research.assert_called_once()


@pytest.mark.asyncio
async def test_generate_market_insight_is_no_longer_supported():
    with pytest.raises(AgentError):
        await dispatch_tool(
            "generate_market_insight",
            {"pairs": ["EUR/USD"]},
            AsyncMock(),
        )
