import pytest
from backend.connectors.fred_connector import InterestRateData
from backend.agent.tools import (
    AgentError,
    TOOL_DEFINITIONS,
    dispatch_tool,
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


def test_tool_definitions_expose_only_intent_tools():
    assert _tool_names(TOOL_DEFINITIONS) == [
        "collect_market_context",
        "analyze_market_context",
        "generate_market_briefing",
    ]


def test_generate_market_briefing_tool_accepts_optional_playbook():
    briefing_tool = next(
        tool
        for tool in TOOL_DEFINITIONS
        if tool["function"]["name"] == "generate_market_briefing"
    )

    properties = briefing_tool["function"]["parameters"]["properties"]
    assert "playbook" in properties
    assert properties["playbook"]["enum"] == [
        "general",
        "fx_carry",
        "macro_rates",
        "morning_note",
        "catalyst_calendar",
    ]


def test_analyze_market_context_tool_accepts_fx_analysis_parameters():
    analysis_tool = next(
        tool
        for tool in TOOL_DEFINITIONS
        if tool["function"]["name"] == "analyze_market_context"
    )

    properties = analysis_tool["function"]["parameters"]["properties"]
    assert "horizon" in properties
    assert "focus" in properties
    assert properties["horizon"]["enum"] == ["intraday", "1w", "1m", "3m"]
    assert "fx_analysis" in properties["analysis_type"]["enum"]


def test_tool_definitions_hide_low_level_tools():
    names = _tool_names(TOOL_DEFINITIONS)
    hidden_names = {
        "get_exchange_rate",
        "get_exchange_rates",
        "get_historical_rates",
        "list_supported_currencies",
        "generate_dashboard",
        "get_fx_news",
        "get_internal_research",
        "get_interest_rate",
        "analyze_fx_economic_correlation",
        "collect_market_data",
        "analyze_market_trends",
        "generate_report",
        "synthesize_research",
        "get_fx_spot",
        "get_fx_history",
        "list_supported_currencies",
    }
    assert hidden_names.isdisjoint(names)


def test_tool_definitions_have_required_fields():
    for tool in TOOL_DEFINITIONS:
        assert tool["type"] == "function"
        assert "name" in tool["function"]
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,tool_args",
    [
        ("get_exchange_rate", {"base": "USD", "target": "EUR"}),
        ("get_exchange_rates", {"base": "USD", "targets": ["EUR", "GBP"]}),
        ("get_historical_rates", {"base": "USD", "targets": ["EUR"], "start_date": "2025-01-01", "end_date": "2025-01-02"}),
        ("list_supported_currencies", {}),
        ("generate_dashboard", {"base": "USD", "targets": ["EUR"], "start_date": "2025-01-01", "end_date": "2025-01-02", "panel_type": "line_trend"}),
        ("get_fx_news", {}),
        ("get_internal_research", {"question": "EUR/USD outlook"}),
        ("get_interest_rate", {"series_id": "DFF"}),
        ("analyze_fx_economic_correlation", {"pair": "EUR/USD", "indicators": ["DFF"]}),
        ("collect_market_data", {"data_type": "rates", "pairs": ["EUR/USD"]}),
        ("analyze_market_trends", {"data": {}, "analysis_type": "trend"}),
        ("generate_report", {"data": {}, "format": "summary"}),
        ("synthesize_research", {"sources": {}}),
    ],
)
async def test_dispatch_rejects_low_level_and_legacy_sub_agent_tools(tool_name, tool_args):
    with pytest.raises(AgentError, match="Unknown tool"):
        await dispatch_tool(tool_name, tool_args, MockConnector())


@pytest.mark.asyncio
async def test_dispatch_unknown_tool_raises_agent_error():
    connector = MockConnector()
    with pytest.raises(AgentError):
        await dispatch_tool("unknown_tool", {}, connector)


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


@pytest.mark.asyncio
async def test_dispatch_generate_market_briefing_passes_playbook():
    connector = MockConnector()
    news = MockNewsConnector()

    result = await dispatch_tool(
        "generate_market_briefing",
        {
            "pairs": ["EUR/USD"],
            "playbook": "fx_carry",
            "include_research": False,
        },
        connector,
        news_connector=news,
    )

    assert result["type"] == "market_briefing"
    assert result["playbook"]["id"] == "fx_carry"
