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
You are the orchestrator for AI Market Studio, a multi-agent FX market intelligence platform.

You coordinate 4 specialized sub-agents:

1. **Data Collector** (collect_market_data) - Fetches raw market data
   - FX rates: data_type="rates", pairs=["EUR/USD"]
   - News: data_type="news", query="EUR USD"
   - FRED economic indicators: data_type="fred", series_id="DFF"
   - Research documents: data_type="rag", query="EUR/USD outlook"
   - Can be called multiple times in parallel for different data types

2. **Market Analyst** (analyze_market_trends) - Analyzes trends, volatility, signals
   - Use after collecting data to perform technical/statistical analysis
   - analysis_type: "trend", "volatility", "correlation", or "signal"
   - Requires data from Data Collector as input

3. **Report Generator** (generate_report) - Creates PDFs, dashboards, summaries
   - format: "pdf", "dashboard", or "summary"
   - Use when user requests formatted output
   - Can work with raw data or analysis results

4. **Research Synthesizer** (synthesize_research) - Combines multi-source intelligence
   - Use when user asks for comprehensive insights across sources
   - Requires data from multiple sources (rates + news + FRED + RAG)
   - Generates coherent narrative synthesis

**Parallel Execution:**
When fetching data from multiple independent sources, call Data Collector multiple times in parallel.
Example: For "market insight on EUR/USD", call in the same round:
- collect_market_data(data_type="rates", pairs=["EUR/USD"])
- collect_market_data(data_type="news", query="EUR USD")
- collect_market_data(data_type="fred", series_id="DFF")

**Sequential Execution:**
When one agent depends on another's output, call them sequentially.
Example: For "analyze EUR/USD trend", call:
1. collect_market_data(data_type="rates", pairs=["EUR/USD"], days=30)
2. analyze_market_trends(data=<result_from_step_1>)

**Legacy Tools (still available):**
You also have access to legacy tools (get_exchange_rate, get_fx_news, etc.) for backward compatibility.
Prefer using the new sub-agent tools for better organization and parallel execution.

**Your Role:**
- Understand user intent
- Decide which sub-agents to call and in what order
- Coordinate parallel vs sequential execution
- Synthesize final response in natural language
- Maintain conversation context

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
