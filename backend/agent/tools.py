from typing import Any, Optional
from backend.connectors.base import MarketDataConnector, ConnectorError
from backend.connectors.news_connector import NewsConnectorBase

# ---------------------------------------------------------------------------
# Tool JSON schemas (sent to GPT-4o as function definitions)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_exchange_rate",
            "description": (
                "Get the exchange rate for a single currency pair. "
                "Use this when the user asks about one specific pair."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "base": {
                        "type": "string",
                        "description": "Base currency ISO 4217 code, e.g. 'EUR'.",
                    },
                    "target": {
                        "type": "string",
                        "description": "Target currency ISO 4217 code, e.g. 'USD'.",
                    },
                    "date": {
                        "type": "string",
                        "description": "Optional date in YYYY-MM-DD format for historical rates.",
                    },
                },
                "required": ["base", "target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_exchange_rates",
            "description": (
                "Get exchange rates for multiple target currencies from a single base. "
                "Use this when the user asks to compare one currency against several others."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "base": {
                        "type": "string",
                        "description": "Base currency ISO 4217 code, e.g. 'USD'.",
                    },
                    "targets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of target currency codes, e.g. ['EUR', 'GBP', 'JPY'].",
                    },
                    "date": {
                        "type": "string",
                        "description": "Optional date in YYYY-MM-DD format for historical rates.",
                    },
                },
                "required": ["base", "targets"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_historical_rates",
            "description": (
                "Retrieve historical daily FX rates for a base currency against one or "
                "more target currencies over a date range. Use when the user asks about "
                "rate trends, historical performance, or wants to compare rates over time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "base": {
                        "type": "string",
                        "description": "ISO 4217 base currency, e.g. USD",
                    },
                    "targets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of target currency codes",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date YYYY-MM-DD",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date YYYY-MM-DD",
                    },
                },
                "required": ["base", "targets", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_supported_currencies",
            "description": "List all currency codes supported by the current data connector.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_dashboard",
            "description": (
                "Generate a visual FX rate trend or comparison dashboard panel. "
                "Use when the user asks to 'show', 'chart', 'plot', 'visualize', "
                "or 'display' exchange rate trends or comparisons over a date range. "
                "Returns historical rate series suitable for chart rendering."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "base": {
                        "type": "string",
                        "description": "Base currency code (e.g. 'USD')",
                    },
                    "targets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Target currency codes (e.g. ['EUR', 'GBP'])",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format",
                    },
                    "panel_type": {
                        "type": "string",
                        "enum": ["line_trend", "bar_comparison"],
                        "description": "Chart type: line_trend for time series, bar_comparison for snapshot comparison",
                    },
                },
                "required": ["base", "targets", "start_date", "end_date", "panel_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fx_news",
            "description": (
                "Fetch recent FX and financial market news headlines. "
                "Use when the user asks about news, what's happening in the market, "
                "why a currency is moving, or current events affecting FX rates."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optional keyword to filter news (e.g. 'EUR/USD', 'Fed', 'inflation', 'BOJ'). Omit to get general FX news.",
                    },
                    "max_items": {
                        "type": "integer",
                        "description": "Maximum number of news items to return. Between 1 and 10. Default is 5.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_market_insight",
            "description": (
                "Gather current spot rates and recent news for a set of currency pairs "
                "to produce a market insight summary. "
                "Use when the user asks for a market overview, briefing, insight, "
                "or what's happening with specific currencies."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pairs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Currency pairs to include, e.g. ['EUR/USD', 'GBP/USD']. Each pair is BASE/TARGET.",
                    },
                    "news_query": {
                        "type": "string",
                        "description": "Optional keyword to filter news (e.g. 'EUR', 'Fed', 'inflation'). Omit for general FX news.",
                    },
                    "max_news": {
                        "type": "integer",
                        "description": "Maximum number of news items to include. Between 1 and 10. Default is 5.",
                    },
                },
                "required": ["pairs"],
            },
        },
    },
]


class AgentError(Exception):
    """Raised when the agent cannot complete a request."""


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

async def dispatch_tool(
    tool_name: str,
    tool_args: dict[str, Any],
    connector: MarketDataConnector,
    news_connector: Optional[NewsConnectorBase] = None,
) -> Any:
    """Execute a tool call and return the result.

    Raises:
        AgentError: If the tool name is unknown.
        ConnectorError: Propagated from the connector layer.
    """
    if tool_name == "get_exchange_rate":
        return await connector.get_exchange_rate(
            base=tool_args["base"],
            target=tool_args["target"],
            date=tool_args.get("date"),
        )
    elif tool_name == "get_exchange_rates":
        return await connector.get_exchange_rates(
            base=tool_args["base"],
            targets=tool_args["targets"],
            date=tool_args.get("date"),
        )
    elif tool_name == "get_historical_rates":
        return await connector.get_historical_rates(
            base=tool_args["base"],
            targets=tool_args["targets"],
            start_date=tool_args["start_date"],
            end_date=tool_args["end_date"],
        )
    elif tool_name == "list_supported_currencies":
        currencies = await connector.list_supported_currencies()
        return {"currencies": currencies}
    elif tool_name == "generate_dashboard":
        raw = await connector.get_historical_rates(
            base=tool_args["base"],
            targets=tool_args["targets"],
            start_date=tool_args["start_date"],
            end_date=tool_args["end_date"],
        )
        sorted_dates = sorted(raw.keys())
        return {
            "type": "dashboard",
            "panel_type": tool_args["panel_type"],
            "base": tool_args["base"].upper(),
            "targets": [t.upper() for t in tool_args["targets"]],
            "start_date": sorted_dates[0] if sorted_dates else tool_args["start_date"],
            "end_date": sorted_dates[-1] if sorted_dates else tool_args["end_date"],
            "series": [
                {"date": date, "rates": raw[date]}
                for date in sorted_dates
            ],
        }
    elif tool_name == "get_fx_news":
        query = tool_args.get("query")
        max_items = min(int(tool_args.get("max_items", 5)), 10)
        if news_connector is None:
            return {"type": "news", "query": query, "items": [], "error": "News connector not available"}
        items = news_connector.get_fx_news(query=query, max_items=max_items)
        return {"type": "news", "query": query, "items": items}
    elif tool_name == "generate_market_insight":
        pairs = tool_args.get("pairs", [])
        news_query = tool_args.get("news_query")
        max_news = min(int(tool_args.get("max_news", 5)), 10)
        # Fetch spot rate for each pair
        rates = []
        for pair in pairs:
            parts = pair.upper().replace("-", "/").split("/")
            if len(parts) == 2:
                base, target = parts
                try:
                    rate_data = await connector.get_exchange_rate(base=base, target=target)
                    rates.append(rate_data)
                except ConnectorError as e:
                    rates.append({"base": base, "target": target, "error": str(e)})
        # Fetch news
        news_items = []
        if news_connector is not None:
            news_items = news_connector.get_fx_news(query=news_query, max_items=max_news)
        return {
            "type": "insight",
            "pairs": pairs,
            "rates": rates,
            "news": news_items,
        }
    else:
        raise AgentError(f"Unknown tool: {tool_name}")
