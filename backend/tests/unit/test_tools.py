import pytest
from backend.agent.tools import TOOL_DEFINITIONS, dispatch_tool, AgentError
from backend.connectors.mock_connector import MockConnector
from backend.connectors.news_connector import MockNewsConnector


def test_tool_definitions_are_valid():
    assert isinstance(TOOL_DEFINITIONS, list)
    assert len(TOOL_DEFINITIONS) == 6
    names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
    assert "get_exchange_rate" in names
    assert "get_exchange_rates" in names
    assert "get_historical_rates" in names
    assert "list_supported_currencies" in names
    assert "generate_dashboard" in names
    assert "get_fx_news" in names


def test_tool_definitions_have_required_fields():
    for tool in TOOL_DEFINITIONS:
        assert tool["type"] == "function"
        assert "name" in tool["function"]
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]


@pytest.mark.asyncio
async def test_dispatch_get_exchange_rate():
    connector = MockConnector()
    result = await dispatch_tool("get_exchange_rate", {"base": "USD", "target": "EUR"}, connector)
    assert result["base"] == "USD"
    assert result["target"] == "EUR"
    assert "rate" in result


@pytest.mark.asyncio
async def test_dispatch_get_exchange_rates():
    connector = MockConnector()
    result = await dispatch_tool("get_exchange_rates", {"base": "USD", "targets": ["EUR", "GBP"]}, connector)
    assert isinstance(result, list)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_dispatch_list_supported_currencies():
    connector = MockConnector()
    result = await dispatch_tool("list_supported_currencies", {}, connector)
    assert "currencies" in result
    assert isinstance(result["currencies"], list)


@pytest.mark.asyncio
async def test_dispatch_get_fx_news_no_connector():
    """get_fx_news with no news_connector returns empty items and error key."""
    connector = MockConnector()
    result = await dispatch_tool("get_fx_news", {}, connector, news_connector=None)
    assert result["type"] == "news"
    assert result["items"] == []
    assert "error" in result


@pytest.mark.asyncio
async def test_dispatch_get_fx_news_with_mock_connector():
    connector = MockConnector()
    news = MockNewsConnector()
    result = await dispatch_tool("get_fx_news", {}, connector, news_connector=news)
    assert result["type"] == "news"
    assert isinstance(result["items"], list)
    assert len(result["items"]) <= 5
    assert result["query"] is None


@pytest.mark.asyncio
async def test_dispatch_get_fx_news_with_query():
    connector = MockConnector()
    news = MockNewsConnector()
    result = await dispatch_tool(
        "get_fx_news", {"query": "Fed", "max_items": 3}, connector, news_connector=news
    )
    assert result["type"] == "news"
    assert result["query"] == "Fed"
    assert len(result["items"]) <= 3
    for item in result["items"]:
        text = item["title"].lower() + item["summary"].lower()
        assert "fed" in text


@pytest.mark.asyncio
async def test_dispatch_get_fx_news_max_items_capped_at_10():
    connector = MockConnector()
    news = MockNewsConnector()
    result = await dispatch_tool(
        "get_fx_news", {"max_items": 999}, connector, news_connector=news
    )
    assert len(result["items"]) <= 10


@pytest.mark.asyncio
async def test_dispatch_unknown_tool_raises_agent_error():
    connector = MockConnector()
    with pytest.raises(AgentError):
        await dispatch_tool("unknown_tool", {}, connector)


@pytest.mark.asyncio
async def test_dispatch_tool_get_historical_rates():
    """dispatch_tool routes get_historical_rates to connector correctly."""
    connector = MockConnector()
    result = await dispatch_tool(
        "get_historical_rates",
        {
            "base": "USD",
            "targets": ["EUR", "GBP"],
            "start_date": "2025-01-01",
            "end_date": "2025-01-03",
        },
        connector,
    )
    assert isinstance(result, dict)
    assert "2025-01-01" in result
    assert "2025-01-03" in result
    assert "EUR" in result["2025-01-01"]
    assert "GBP" in result["2025-01-01"]
