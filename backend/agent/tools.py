from typing import Any, Optional

from backend.connectors.base import MarketDataConnector
from backend.connectors.news_connector import NewsConnectorBase


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "collect_market_context",
            "description": "Collect requested FX rates, news, FRED indicators, and research context without analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pairs": {"type": "array", "items": {"type": "string"}},
                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["rates", "news", "fred", "research"],
                        },
                    },
                    "days": {"type": "integer"},
                    "fred_series_ids": {"type": "array", "items": {"type": "string"}},
                    "query": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_market_context",
            "description": "Analyze collected or supplied FX market context without generating a full briefing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pairs": {"type": "array", "items": {"type": "string"}},
                    "analysis_type": {
                        "type": "string",
                        "enum": [
                            "trend",
                            "volatility",
                            "economic_relationship",
                            "general",
                            "fx_analysis",
                        ],
                    },
                    "days": {"type": "integer"},
                    "horizon": {
                        "type": "string",
                        "enum": ["intraday", "1w", "1m", "3m"],
                    },
                    "focus": {"type": "string"},
                    "context": {"type": "object"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_market_briefing",
            "description": "Generate a structured market briefing by coordinating context collection, analysis, and synthesis internally.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pairs": {"type": "array", "items": {"type": "string"}},
                    "playbook": {
                        "type": "string",
                        "enum": [
                            "general",
                            "fx_carry",
                            "macro_rates",
                            "morning_note",
                            "catalyst_calendar",
                        ],
                    },
                    "focus": {"type": "string"},
                    "include_news": {"type": "boolean"},
                    "include_fred": {"type": "boolean"},
                    "include_research": {"type": "boolean"},
                    "fred_series_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["pairs"],
            },
        },
    },
]


class AgentError(Exception):
    """Raised when the agent cannot complete a request."""


async def dispatch_tool(
    tool_name: str,
    tool_args: dict[str, Any],
    connector: MarketDataConnector,
    news_connector: Optional[NewsConnectorBase] = None,
    fred_connector=None,
    rag_connector=None,
) -> Any:
    """Execute an approved workflow tool call and return the result."""
    if tool_name == "collect_market_context":
        from backend.agent.workflows import collect_market_context

        return await collect_market_context(
            pairs=tool_args.get("pairs"),
            sources=tool_args.get("sources"),
            days=tool_args.get("days"),
            fred_series_ids=tool_args.get("fred_series_ids"),
            query=tool_args.get("query"),
            connector=connector,
            news_connector=news_connector,
            fred_connector=fred_connector,
            rag_connector=rag_connector,
        )
    if tool_name == "analyze_market_context":
        from backend.agent.workflows import analyze_market_context

        return await analyze_market_context(
            context=tool_args.get("context"),
            pairs=tool_args.get("pairs"),
            analysis_type=tool_args.get("analysis_type", "general"),
            days=tool_args.get("days"),
            horizon=tool_args.get("horizon"),
            focus=tool_args.get("focus"),
            connector=connector,
            news_connector=news_connector,
            fred_connector=fred_connector,
            rag_connector=rag_connector,
        )
    if tool_name == "generate_market_briefing":
        from backend.agent.workflows import generate_market_briefing

        return await generate_market_briefing(
            pairs=tool_args.get("pairs") or [],
            playbook=tool_args.get("playbook"),
            focus=tool_args.get("focus"),
            include_news=tool_args.get("include_news", True),
            include_fred=tool_args.get("include_fred", False),
            include_research=tool_args.get("include_research", True),
            fred_series_ids=tool_args.get("fred_series_ids"),
            connector=connector,
            news_connector=news_connector,
            fred_connector=fred_connector,
            rag_connector=rag_connector,
        )

    raise AgentError(f"Unknown tool: {tool_name}")
