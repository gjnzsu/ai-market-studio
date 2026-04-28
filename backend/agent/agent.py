import json
import logging
from typing import Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from backend.config import settings
from backend.connectors.base import MarketDataConnector, ConnectorError
from backend.connectors.news_connector import NewsConnectorBase
from backend.agent.tools import TOOL_DEFINITIONS, dispatch_tool, AgentError
from ai_sre_observability import get_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an AI assistant for AI Market Studio, an FX market intelligence platform.

You have access to these tools:

**FX Rate Tools:**
- get_exchange_rate: Get spot rate for a single currency pair
- get_exchange_rates: Get rates for multiple target currencies from one base
- get_historical_rates: Get historical rates over a date range
- generate_dashboard: Create visual charts for rate trends

**Market Data Tools:**
- get_fx_news: Fetch recent FX and financial news
- get_interest_rate: Get FRED economic indicators (federal funds rate, treasury rates, etc.)
- generate_market_insight: Get comprehensive market insight with rates + news for currency pairs

**Analysis Tools:**
- analyze_fx_economic_correlation: Analyze correlation between FX pairs and economic indicators

**Utility:**
- list_supported_currencies: List all supported currency codes

**When to use generate_market_insight:**
Use this tool when the user asks for a market overview, briefing, insight, or what's happening with specific currencies. It automatically fetches both rates and news in one call.

Be concise, accurate, and helpful. Always cite your data sources.
"""

MAX_TOOL_ROUNDS = 3  # Reduced from 5 to prevent long sequential chains


def _summarise_tool_result(result: dict) -> dict:
    """Return a compact GPT-4o-friendly summary for structured UI payloads."""
    rtype = result.get("type")
    if rtype == "insight":
        rate_lines = []
        for r in result.get("rates", []):
            if "error" in r:
                rate_lines.append(f"{r['base']}/{r['target']}: unavailable")
            else:
                rate_lines.append(f"{r['base']}/{r['target']}: {r['rate']} ({r.get('date', '')})")
        news_titles = [n["title"] for n in result.get("news", [])]
        return {"rates": rate_lines, "news_headlines": news_titles}
    if rtype == "dashboard":
        return {"panel_type": result.get("panel_type"), "pairs": result.get("targets"), "series_count": len(result.get("series", []))}
    if rtype == "news":
        return {"headlines": [n["title"] for n in result.get("items", [])]}
    if result.get("type") == "rag":
        sources_list = [s["name"] for s in result.get("sources", [])]
        return {"type": "rag", "sources": sources_list}
    return result


async def run_agent(
    message: str,
    history: Optional[list[dict]] = None,
    connector: Optional[MarketDataConnector] = None,
    client: Optional[AsyncOpenAI] = None,
    news_connector: Optional[NewsConnectorBase] = None,
    fred_connector = None,
    rag_connector = None,
) -> dict:
    """Run the GPT-4o function-calling agent loop.

    Args:
        message: The user's latest message.
        history: Prior conversation turns as list of {role, content} dicts.
        connector: MarketDataConnector instance to use for tool calls.
        client: Optional AsyncOpenAI client (injectable for testing).

    Returns:
        dict with keys: reply (str), data (any), tool_used (str or None)
    """
    if client is None:
        import httpx
        client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            base_url=settings.openai_base_url,
            http_client=httpx.AsyncClient(trust_env=False),
        )

    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message})

    last_tool_used: Optional[str] = None
    last_tool_data = None

    # Get observability client (graceful degradation)
    try:
        obs = get_client()
    except RuntimeError:
        obs = None
        logger.warning("Observability not initialized, skipping metrics")

    # Track token accumulation across all LLM calls
    total_prompt_tokens = 0
    total_completion_tokens = 0

    # Wrap agent loop with observability tracking
    if obs:
        async with obs.track_llm_call(
            provider="openai",
            model=settings.openai_model
        ) as tracker:
            for _ in range(MAX_TOOL_ROUNDS):
                logger.info(f"[Agent] Making request with model: {settings.openai_model}")
                response = await client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                )

                # Accumulate tokens
                if response.usage:
                    total_prompt_tokens += response.usage.prompt_tokens
                    total_completion_tokens += response.usage.completion_tokens

                choice = response.choices[0]
                msg = choice.message
                messages.append(msg.model_dump(exclude_unset=True))

                if choice.finish_reason == "tool_calls" and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        logger.info("Tool call: %s args=%s", tool_name, tool_args)

                        try:
                            result = await dispatch_tool(tool_name, tool_args, connector, news_connector, fred_connector, rag_connector)
                            last_tool_used = tool_name
                            last_tool_data = result
                            # For structured UI payloads, send GPT-4o a compact summary
                            # instead of the full JSON so it doesn't echo the raw payload.
                            if isinstance(result, dict) and result.get("type") in ("insight", "dashboard", "news", "rag"):
                                tool_result_content = json.dumps(_summarise_tool_result(result))
                            else:
                                tool_result_content = json.dumps(result)
                        except ConnectorError as e:
                            logger.warning("Connector error: %s", e)
                            tool_result_content = json.dumps({"error": str(e)})
                        except AgentError as e:
                            logger.error("Agent error: %s", e)
                            tool_result_content = json.dumps({"error": str(e)})

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result_content,
                        })
                    continue

                # Final text response
                reply = msg.content or ""
                # Set accumulated totals before exiting context
                tracker.prompt_tokens = total_prompt_tokens
                tracker.completion_tokens = total_completion_tokens
                return {"reply": reply, "data": last_tool_data, "tool_used": last_tool_used}

            # Max rounds reached - set totals before exiting
            tracker.prompt_tokens = total_prompt_tokens
            tracker.completion_tokens = total_completion_tokens
    else:
        # No observability - run agent normally
        for _ in range(MAX_TOOL_ROUNDS):
            logger.info(f"[Agent] Making request with model: {settings.openai_model}")
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )

            choice = response.choices[0]
            msg = choice.message
            messages.append(msg.model_dump(exclude_unset=True))

            if choice.finish_reason == "tool_calls" and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    logger.info("Tool call: %s args=%s", tool_name, tool_args)

                    try:
                        result = await dispatch_tool(tool_name, tool_args, connector, news_connector, fred_connector, rag_connector)
                        last_tool_used = tool_name
                        last_tool_data = result
                        # For structured UI payloads, send GPT-4o a compact summary
                        # instead of the full JSON so it doesn't echo the raw payload.
                        if isinstance(result, dict) and result.get("type") in ("insight", "dashboard", "news", "rag"):
                            tool_result_content = json.dumps(_summarise_tool_result(result))
                        else:
                            tool_result_content = json.dumps(result)
                    except ConnectorError as e:
                        logger.warning("Connector error: %s", e)
                        tool_result_content = json.dumps({"error": str(e)})
                    except AgentError as e:
                        logger.error("Agent error: %s", e)
                        tool_result_content = json.dumps({"error": str(e)})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result_content,
                    })
                continue

            # Final text response
            reply = msg.content or ""
            return {"reply": reply, "data": last_tool_data, "tool_used": last_tool_used}

    return {
        "reply": "I was unable to complete your request after several attempts. Please try again.",
        "data": None,
        "tool_used": last_tool_used,
    }
