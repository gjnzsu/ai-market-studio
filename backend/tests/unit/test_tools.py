import pytest
from backend.agent.tools import TOOL_DEFINITIONS, dispatch_tool, AgentError
from backend.connectors.mock_connector import MockConnector


def test_tool_definitions_are_valid():
    assert isinstance(TOOL_DEFINITIONS, list)
    assert len(TOOL_DEFINITIONS) == 4
    names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
    assert "get_exchange_rate" in names
    assert "get_exchange_rates" in names
    assert "get_historical_rates" in names
    assert "list_supported_currencies" in names


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
