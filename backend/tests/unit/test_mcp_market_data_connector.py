import pytest

from backend.connectors.base import RateFetchError
from backend.connectors.mcp_market_data import MCPMarketDataConnector


class FakeMCPClient:
    def __init__(self, responses=None, error=None):
        self.responses = responses or {}
        self.error = error
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.error:
            raise self.error
        return self.responses[name]


@pytest.mark.asyncio
async def test_mcp_market_data_connector_normalizes_spot_response():
    client = FakeMCPClient(
        {
            "get_fx_spot": {
                "pair": "EUR/USD",
                "base": "EUR",
                "target": "USD",
                "rate": 1.0865,
                "date": "2026-06-14",
                "source": "mcp-mock-market-data",
            }
        }
    )
    connector = MCPMarketDataConnector(client=client)

    result = await connector.get_exchange_rate("EUR", "USD")

    assert client.calls == [("get_fx_spot", {"pair": "EUR/USD", "date": None})]
    assert result == {
        "base": "EUR",
        "target": "USD",
        "rate": 1.0865,
        "date": "2026-06-14",
        "source": "mcp-mock-market-data",
    }


@pytest.mark.asyncio
async def test_mcp_market_data_connector_normalizes_historical_response():
    client = FakeMCPClient(
        {
            "get_fx_history": {
                "pair": "EUR/USD",
                "base": "EUR",
                "target": "USD",
                "rates": {
                    "2026-06-10": 1.08,
                    "2026-06-11": 1.081,
                },
                "source": "mcp-mock-market-data",
            }
        }
    )
    connector = MCPMarketDataConnector(client=client)

    result = await connector.get_historical_rates(
        "EUR",
        ["USD"],
        "2026-06-10",
        "2026-06-11",
    )

    assert client.calls == [
        (
            "get_fx_history",
            {
                "pair": "EUR/USD",
                "start_date": "2026-06-10",
                "end_date": "2026-06-11",
            },
        )
    ]
    assert result == {
        "2026-06-10": {"USD": 1.08},
        "2026-06-11": {"USD": 1.081},
    }


@pytest.mark.asyncio
async def test_mcp_market_data_connector_lists_supported_currencies():
    client = FakeMCPClient({"list_supported_currencies": ["USD", "EUR", "JPY"]})
    connector = MCPMarketDataConnector(client=client)

    result = await connector.list_supported_currencies()

    assert client.calls == [("list_supported_currencies", {})]
    assert result == ["USD", "EUR", "JPY"]


@pytest.mark.asyncio
async def test_mcp_market_data_connector_wraps_tool_errors():
    connector = MCPMarketDataConnector(client=FakeMCPClient(error=RuntimeError("down")))

    with pytest.raises(RateFetchError, match="MCP market data tool failed"):
        await connector.get_exchange_rate("EUR", "USD")
