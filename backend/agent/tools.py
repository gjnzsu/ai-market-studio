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
    {
        "type": "function",
        "function": {
            "name": "get_internal_research",
            "description": "Search internal research documents (PDFs, Jira, Confluence) for market insights.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The specific query to search in internal docs."}
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_interest_rate",
            "description": (
                "Get current or historical interest rates from the Federal Reserve (FRED API). "
                "Use when the user asks about federal funds rate, treasury rates, mortgage rates, or other economic indicators."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "series_id": {
                        "type": "string",
                        "description": "FRED series ID (e.g. 'DFF' for Effective Federal Funds Rate, 'DGS10' for 10-Year Treasury, 'T10Y2Y' for 10Y-2Y spread, 'MORTGAGE30US' for 30-Year Mortgage Rate)",
                    },
                    "date": {
                        "type": "string",
                        "description": "Optional specific date in YYYY-MM-DD format. If omitted, returns latest available data.",
                    },
                },
                "required": ["series_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_fx_economic_correlation",
            "description": (
                "Analyze correlation between FX pair movements and economic indicators "
                "(interest rates, GDP, inflation) over a time period. Use this when the user "
                "asks why a currency is moving or wants to understand economic drivers of FX trends."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pair": {
                        "type": "string",
                        "description": "Currency pair in format BASE/TARGET (e.g., 'EUR/USD', 'GBP/USD')",
                    },
                    "indicators": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "FRED series IDs to correlate (e.g., ['DFF', 'DGS10', 'CPIAUCSL']). "
                            "Common: DFF=Fed Funds, DGS10=10Y Treasury, CPIAUCSL=CPI, GDPC1=GDP"
                        ),
                    },
                    "days": {
                        "type": "integer",
                        "description": "Lookback period in days (default: 90, min: 30, max: 365)",
                    },
                },
                "required": ["pair", "indicators"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "collect_market_data",
            "description": (
                "Fetch market data from various sources (FX rates, news, FRED economic indicators, research documents). "
                "Can be called multiple times in parallel for different data types."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "data_type": {
                        "type": "string",
                        "enum": ["rates", "news", "fred", "rag"],
                        "description": "Type of data to collect"
                    },
                    "pairs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Currency pairs (e.g., ['EUR/USD', 'GBP/USD'])"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days of historical data"
                    },
                    "series_id": {
                        "type": "string",
                        "description": "FRED series ID (e.g., 'DFF', 'DGS10')"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query for news or RAG"
                    }
                },
                "required": ["data_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_market_trends",
            "description": (
                "Analyze FX market data for trends, volatility, correlations, and trading signals. "
                "Use after collecting data to perform technical/statistical analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": "Market data from Data Collector"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["trend", "volatility", "correlation", "signal"],
                        "description": "Type of analysis to perform"
                    },
                    "context": {
                        "type": "object",
                        "description": "Additional context (news, economic indicators)"
                    }
                },
                "required": ["data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": (
                "Generate formatted reports, dashboards, or summaries from market data and analysis. "
                "Use when user requests formatted output."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": "Market data to include in report"
                    },
                    "analysis": {
                        "type": "object",
                        "description": "Analysis results to include"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["pdf", "dashboard", "summary"],
                        "description": "Output format"
                    },
                    "title": {
                        "type": "string",
                        "description": "Report title"
                    }
                },
                "required": ["data", "format"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "synthesize_research",
            "description": (
                "Combine multi-source market intelligence (rates, news, economic data, research) into coherent insights. "
                "Use when user asks for comprehensive insights across sources."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sources": {
                        "type": "object",
                        "description": "Data from multiple sources (rates, news, fred, rag)"
                    },
                    "focus": {
                        "type": "string",
                        "description": "Aspect to emphasize (e.g., 'interest rates', 'technical analysis')"
                    },
                    "max_sources": {
                        "type": "integer",
                        "description": "Maximum number of sources to include"
                    }
                },
                "required": ["sources"]
            }
        }
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
    fred_connector = None,
    rag_connector = None,
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
        # Batch fetch: group targets by base to minimise API calls.
        # Special case: pairs sharing the same target are fetched in one call
        # by using that target as base and inverting (avoids per-pair HTTP hits).
        from collections import defaultdict
        base_to_targets: dict = defaultdict(list)
        target_to_bases: dict = defaultdict(list)
        valid_pairs: list = []
        for pair in pairs:
            parts = pair.upper().replace("-", "/").split("/")
            if len(parts) == 2:
                base, target = parts
                valid_pairs.append((base, target))
                target_to_bases[target].append(base)

        rates = []
        fetched: dict = {}  # (base, target) -> rate_data

        # For each unique target that has multiple bases, fetch all bases at once
        # using that target as the connector base (one API call instead of N).
        for common_target, bases in target_to_bases.items():
            if len(bases) >= 1:
                try:
                    batch = await connector.get_exchange_rates(base=common_target, targets=bases)
                    for item in batch:
                        # item is common_target→base; we want base→common_target = 1/rate
                        b, t = item["base"], item["target"]
                        # b == common_target, t == original base
                        inverted = {
                            "base": t,
                            "target": b,
                            "rate": round(1.0 / item["rate"], 6) if item.get("rate") else None,
                            "date": item.get("date"),
                            "source": item.get("source"),
                        }
                        fetched[(t, b)] = inverted
                except ConnectorError as e:
                    for base in bases:
                        fetched[(base, common_target)] = {"base": base, "target": common_target, "error": str(e)}

        for base, target in valid_pairs:
            if (base, target) in fetched:
                rates.append(fetched[(base, target)])
            else:
                rates.append({"base": base, "target": target, "error": "Rate not fetched"})
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
    elif tool_name == "get_internal_research":
        from backend.connectors.rag_connector import RAGConnector
        rag = RAGConnector()
        return await rag.query_research(tool_args.get("question"))
    elif tool_name == "get_interest_rate":
        if fred_connector is None:
            raise AgentError("FRED connector not available. Please configure FRED_API_KEY.")
        series_id = tool_args.get("series_id")
        date = tool_args.get("date")
        if not series_id:
            raise AgentError("series_id is required for get_interest_rate")
        result = await fred_connector.get_current_rate(series_id=series_id, date=date)
        return result.model_dump()
    elif tool_name == "analyze_fx_economic_correlation":
        from backend.connectors.correlation_connector import CorrelationConnector
        from backend.connectors.fred_connector import FREDConnector

        correlation_connector = CorrelationConnector(
            market_connector=connector,
            fred_connector=FREDConnector()
        )

        pair = tool_args.get("pair")
        indicators = tool_args.get("indicators")
        days = tool_args.get("days", 90)

        if not pair:
            raise AgentError("pair is required for analyze_fx_economic_correlation")
        if not indicators:
            raise AgentError("indicators is required for analyze_fx_economic_correlation")

        result = await correlation_connector.analyze_correlation(
            pair=pair,
            indicators=indicators,
            days=days
        )

        return {
            "type": "economic_correlation",
            "data": result
        }
    elif tool_name == "collect_market_data":
        from backend.agents import collect_market_data
        return await collect_market_data(
            data_type=tool_args["data_type"],
            pairs=tool_args.get("pairs"),
            days=tool_args.get("days"),
            series_id=tool_args.get("series_id"),
            query=tool_args.get("query"),
            connector=connector,
            news_connector=news_connector,
            fred_connector=fred_connector,
            rag_connector=rag_connector
        )

    elif tool_name == "analyze_market_trends":
        from backend.agents import analyze_market_trends
        return await analyze_market_trends(
            data=tool_args["data"],
            analysis_type=tool_args.get("analysis_type", "trend"),
            context=tool_args.get("context")
        )

    elif tool_name == "generate_report":
        from backend.agents import generate_report
        return await generate_report(
            data=tool_args["data"],
            analysis=tool_args.get("analysis"),
            format=tool_args["format"],
            title=tool_args.get("title")
        )

    elif tool_name == "synthesize_research":
        from backend.agents import synthesize_research
        return await synthesize_research(
            sources=tool_args["sources"],
            focus=tool_args.get("focus"),
            max_sources=tool_args.get("max_sources", 10)
        )
    else:
        raise AgentError(f"Unknown tool: {tool_name}")
