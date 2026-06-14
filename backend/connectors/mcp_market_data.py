import json
from typing import Any, Optional, Protocol

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from backend.connectors.base import MarketDataConnector, RateFetchError


class MCPToolClient(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool and return a normalized Python value."""


class MCPStdioToolClient:
    """Small MCP stdio client wrapper used by the market data connector."""

    def __init__(self, command: str, args: Optional[list[str]] = None) -> None:
        self.command = command
        self.args = args or []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        server_params = StdioServerParameters(command=self.command, args=self.args)
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                return _extract_tool_result(result)


def _extract_tool_result(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured

    content = getattr(result, "content", None)
    if not content:
        return result

    first = content[0]
    text = getattr(first, "text", None)
    if text is None:
        return first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


class MCPMarketDataConnector(MarketDataConnector):
    """Market data connector backed by an MCP market data server."""

    def __init__(self, client: MCPToolClient) -> None:
        self.client = client

    async def get_exchange_rate(
        self,
        base: str,
        target: str,
        date: Optional[str] = None,
    ) -> dict:
        try:
            data = await self.client.call_tool(
                "get_fx_spot",
                {"pair": f"{base.upper()}/{target.upper()}", "date": date},
            )
            return {
                "base": data["base"],
                "target": data["target"],
                "rate": float(data["rate"]),
                "date": data["date"],
                "source": data["source"],
            }
        except Exception as exc:
            raise RateFetchError(f"MCP market data tool failed: {exc}") from exc

    async def get_exchange_rates(
        self,
        base: str,
        targets: list[str],
        date: Optional[str] = None,
    ) -> list[dict]:
        return [
            await self.get_exchange_rate(base=base, target=target, date=date)
            for target in targets
        ]

    async def list_supported_currencies(self) -> list[str]:
        try:
            data = await self.client.call_tool("list_supported_currencies", {})
            return list(data)
        except Exception as exc:
            raise RateFetchError(f"MCP market data tool failed: {exc}") from exc

    async def get_historical_rates(
        self,
        base: str,
        targets: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, dict[str, float]]:
        result: dict[str, dict[str, float]] = {}
        try:
            for target in targets:
                data = await self.client.call_tool(
                    "get_fx_history",
                    {
                        "pair": f"{base.upper()}/{target.upper()}",
                        "start_date": start_date,
                        "end_date": end_date,
                    },
                )
                target_code = data["target"]
                for date, rate in data["rates"].items():
                    result.setdefault(date, {})[target_code] = float(rate)
            return result
        except Exception as exc:
            raise RateFetchError(f"MCP market data tool failed: {exc}") from exc
