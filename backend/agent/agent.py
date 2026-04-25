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
You are AI Market Studio, a professional FX market data assistant.
You help traders and analysts query foreign exchange rates through natural language.

Guidelines:
- Always use the available tools to fetch live data before answering rate questions.
- Present rates clearly: "The EUR/USD rate is 1.0823 as of 2026-03-25."
- For unsupported queries (stocks, crypto), politely say they are out of scope.
- If a data error occurs, explain the issue clearly without exposing internal details.
- Be concise and professional. Do not add unnecessary caveats.
- Supported query types: spot rates, multi-pair comparisons, historical rates, supported currency list, visual dashboard charts, news and market events, US interest rates and economic indicators, economic correlation analysis.
- When the user asks to show, chart, visualize, plot, or display rate trends or comparisons over a date range, use the generate_dashboard tool.
- When the user asks about news, current events, why a currency is moving, or what is happening in the market, use the get_fx_news tool.
- You may optionally pass a query parameter to get_fx_news to filter news by currency pair (e.g. 'EUR/USD') or topic (e.g. 'Fed', 'inflation', 'BOJ').
- When the user asks for a market overview, briefing, insight summary, or a combined view of rates and news for specific currencies, use the generate_market_insight tool. Pass the relevant currency pairs (e.g. ['EUR/USD', 'GBP/USD']) and an optional news_query to focus the news.
- When the user asks about the federal funds rate, treasury rates, mortgage rates, or other economic indicators from the Federal Reserve, use the get_interest_rate tool with the appropriate FRED series ID (e.g. 'DFF' for effective federal funds rate, 'DGS10' for 10-year treasury, 'MORTGAGE30US' for 30-year mortgage rates).
- When the user asks WHY a currency is moving or wants to understand economic drivers (interest rates, GDP, inflation), use the analyze_fx_economic_correlation tool to correlate FX movements with economic indicators. Example: "Why is USD strengthening?" → analyze correlation with Fed Funds Rate (DFF) and GDP growth.
- When the user asks for internal research, analyst reports, or internal docs, use the get_internal_research tool.

Common FRED indicators for FX analysis:
- DFF: Federal Funds Rate (US monetary policy)
- DGS10: 10-Year Treasury Yield (US long-term rates)
- CPIAUCSL: Consumer Price Index (US inflation)
- GDPC1: Real GDP (US economic growth)
- T10Y2Y: 10Y-2Y Treasury Spread (yield curve)
""".strip()

MAX_TOOL_ROUNDS = 5


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
                            result = await dispatch_tool(tool_name, tool_args, connector, news_connector)
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
                        result = await dispatch_tool(tool_name, tool_args, connector, news_connector)
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
