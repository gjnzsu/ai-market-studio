import pytest
from backend.connectors.fred_connector import InterestRateData
from backend.agent.tools import (
    AgentError,
    LEGACY_TOOL_DEFINITIONS,
    TOOL_DEFINITIONS,
    WORKFLOW_TOOL_DEFINITIONS,
    dispatch_tool,
    get_tool_definitions,
)
from backend.connectors.mock_connector import MockConnector
from backend.connectors.news_connector import MockNewsConnector


def _tool_names(tools):
    return [tool["function"]["name"] for tool in tools]


class MockFredConnector:
    async def get_current_rate(self, series_id: str, date: str | None = None):
        return InterestRateData(
            series_id=series_id,
            series_name="Effective Federal Funds Rate (daily)",
            date=date or "2026-05-20",
            value=4.33,
            unit="percent",
            source="FRED (Federal Reserve Economic Data)",
        )


def test_legacy_tool_definitions_exclude_workflow_and_deprecated_tools():
    names = _tool_names(LEGACY_TOOL_DEFINITIONS)
    assert "get_exchange_rate" in names
    assert "get_exchange_rates" in names
    assert "get_historical_rates" in names
    assert "list_supported_currencies" in names
    assert "generate_dashboard" in names
    assert "get_fx_news" in names
    assert "generate_market_insight" not in names
    assert "get_internal_research" in names
    assert "get_interest_rate" in names
    assert "analyze_fx_economic_correlation" in names
    assert "collect_market_data" not in names
    assert "analyze_market_trends" not in names
    assert "generate_report" not in names
    assert "synthesize_research" not in names
    assert "collect_market_context" not in names


def test_workflow_tool_definitions_expose_only_intent_tools():
    assert _tool_names(WORKFLOW_TOOL_DEFINITIONS) == [
        "collect_market_context",
        "analyze_market_context",
        "generate_market_briefing",
    ]


def test_get_tool_definitions_selects_by_agent_mode():
    assert get_tool_definitions("legacy") == LEGACY_TOOL_DEFINITIONS
    assert get_tool_definitions("workflow") == WORKFLOW_TOOL_DEFINITIONS


def test_tool_definitions_alias_remains_legacy_compatible():
    assert TOOL_DEFINITIONS == LEGACY_TOOL_DEFINITIONS


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


@pytest.mark.asyncio
async def test_dispatch_get_interest_rate():
    """get_interest_rate tool dispatches to FREDConnector and returns rate data."""
    result = await dispatch_tool(
        "get_interest_rate",
        {"series_id": "DFF"},
        MockConnector(),
        fred_connector=MockFredConnector(),
    )
    assert isinstance(result, dict)
    assert "series_id" in result
    assert "series_name" in result
    assert "date" in result
    assert "value" in result
    assert "unit" in result
    assert result["series_id"] == "DFF"
    assert result["unit"] == "percent"
    assert result["source"] == "FRED (Federal Reserve Economic Data)"


@pytest.mark.asyncio
async def test_dispatch_get_interest_rate_missing_series_id():
    """get_interest_rate raises AgentError if series_id is missing."""
    with pytest.raises(AgentError) as exc_info:
        await dispatch_tool(
            "get_interest_rate",
            {},
            MockConnector(),
        )
    assert "series_id is required" in str(exc_info.value)


@pytest.mark.asyncio
async def test_dispatch_collect_market_context():
    connector = MockConnector()

    result = await dispatch_tool(
        "collect_market_context",
        {"pairs": ["EUR/USD"], "sources": ["rates"]},
        connector,
    )

    assert result["type"] == "market_context"
    assert result["context"]["rates"][0]["base"] == "EUR"


@pytest.mark.asyncio
async def test_dispatch_analyze_market_context():
    connector = MockConnector()
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

    result = await dispatch_tool(
        "analyze_market_context",
        {"context": context, "analysis_type": "trend"},
        connector,
    )

    assert result["type"] == "market_analysis"
    assert "analysis" in result


@pytest.mark.asyncio
async def test_dispatch_generate_market_briefing():
    connector = MockConnector()
    news = MockNewsConnector()

    result = await dispatch_tool(
        "generate_market_briefing",
        {"pairs": ["EUR/USD"], "include_research": False},
        connector,
        news_connector=news,
    )

    assert result["type"] == "market_briefing"
    assert result["pairs"] == ["EUR/USD"]
