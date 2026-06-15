import json
import logging
from typing import Literal, Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from backend.config import settings
from backend.connectors.base import MarketDataConnector, ConnectorError
from backend.connectors.news_connector import NewsConnectorBase
from backend.agent.tools import get_tool_definitions, dispatch_tool, AgentError
from ai_sre_observability import get_client

logger = logging.getLogger(__name__)

WORKFLOW_SYSTEM_PROMPT = """
You are an AI assistant for AI Market Studio using intent-level market workflows.

Use collect_market_context for data-only market requests, analyze_market_context
for trend, volatility, signal, or economic relationship analysis, and
generate_market_briefing for market insight, overview, briefing, explanation,
or multi-source synthesis requests.

Be concise, accurate, and helpful. Always cite your data sources.
"""

AgentMode = Literal["workflow"]


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

        # Add research summary
        research_docs = []
        for r in result.get("research", []):
            doc_name = r.get("name") or r.get("title", "Unknown")
            research_docs.append(doc_name)

        return {
            "rates": rate_lines,
            "news_headlines": news_titles,
            "research_documents": research_docs,
        }
    if rtype == "market_briefing":
        context = result.get("context", {}).get("context", {})
        news_items = context.get("news", [])
        research = context.get("research", {})
        sources = research.get("sources", []) if isinstance(research, dict) else []
        return {
            "pairs": result.get("pairs", []),
            "playbook": result.get("playbook"),
            "analysis": result.get("analysis", {}),
            "news_headlines": [item.get("title") for item in news_items],
            "research_documents": [source.get("name") for source in sources],
            "data_gaps": result.get("data_gaps", []),
            "source_grounding": result.get("source_grounding", {}),
            "specialist_data": result.get("specialist_data"),
            "carry_metrics": result.get("carry_metrics"),
            "warnings": result.get("warnings", []),
        }
    if rtype == "market_context":
        context = result.get("context", {})
        return {
            "rates": [
                f"{rate.get('base')}/{rate.get('target')}: {rate.get('rate')} ({rate.get('date')})"
                for rate in context.get("rates", [])
            ],
            "historical_series": [
                {
                    "pair": item.get("pair"),
                    "observations": len(item.get("series", [])),
                    "start_date": item.get("start_date"),
                    "end_date": item.get("end_date"),
                }
                for item in context.get("historical_rates", [])
            ],
            "news_headlines": [
                item.get("title") for item in context.get("news", [])
            ],
            "fred_rates": [
                {
                    "series_id": item.get("series_id"),
                    "series_name": item.get("series_name"),
                    "date": item.get("date"),
                    "value": item.get("value"),
                    "unit": item.get("unit"),
                    "source": item.get("source"),
                }
                for item in context.get("fred", [])
            ],
            "research_documents": [
                source.get("name")
                for source in context.get("research", {}).get("sources", [])
            ]
            if isinstance(context.get("research"), dict)
            else [],
            "warnings": result.get("warnings", []),
        }
    if rtype == "market_analysis":
        analysis = result.get("analysis", {})
        return {
            "analysis_type": analysis.get("analysis_type"),
            "pairs": analysis.get("pairs"),
            "summary": analysis.get("summary") or analysis.get("result"),
            "warnings": result.get("warnings", []),
        }
    if rtype == "dashboard":
        return {"panel_type": result.get("panel_type"), "pairs": result.get("targets"), "series_count": len(result.get("series", []))}
    if rtype == "news":
        return {"headlines": [n["title"] for n in result.get("items", [])]}
    if result.get("type") == "rag":
        sources_list = [s["name"] for s in result.get("sources", [])]
        return {"type": "rag", "sources": sources_list}
    return result


def _fallback_reply_from_tool_data(data) -> str:
    if not isinstance(data, dict):
        return (
            "I collected the requested workflow data, but could not generate a final "
            "narrative response before the step limit."
        )
    rtype = data.get("type")
    if rtype == "market_analysis":
        analysis = data.get("analysis", {})
        pair_rows = analysis.get("pairs") or []
        if pair_rows:
            lines = [
                f"{row.get('pair')}: {row.get('trend_direction', 'trend')} "
                f"over {row.get('observations')} observations "
                f"({row.get('change_pct')}% change, {row.get('volatility_pct')}% volatility)."
                for row in pair_rows
            ]
            return "Trend analysis completed: " + " ".join(lines)
        return analysis.get("summary") or "Market analysis completed."
    if rtype == "market_context":
        context = data.get("context", {})
        sources = ", ".join(context.keys()) or "requested sources"
        return f"Market context collected successfully with {sources}."
    if rtype == "market_briefing":
        pairs = ", ".join(data.get("pairs", []))
        playbook = data.get("playbook", {}).get("display_name") or "market briefing"
        return f"{playbook} completed for {pairs}."
    if rtype == "rag":
        count = len(data.get("sources", []))
        return f"Research retrieval completed with {count} source document(s)."
    return "Workflow data collected successfully."


def _fred_reply_from_market_context(data: dict) -> Optional[str]:
    context = data.get("context", {}) if isinstance(data, dict) else {}
    fred_rates = context.get("fred", []) if isinstance(context, dict) else []
    if not fred_rates:
        return None
    rate = fred_rates[0]
    value = rate.get("value")
    if value is None:
        return None
    series_name = rate.get("series_name") or rate.get("series_id") or "FRED rate"
    series_id = rate.get("series_id")
    date = rate.get("date")
    unit = rate.get("unit") or "percent"
    label = f"{series_name} ({series_id})" if series_id else series_name
    return f"{label} is {value} {unit} as of {date}. Source: FRED."


def _reply_denies_available_data(reply: str) -> bool:
    lowered = reply.lower()
    denial_markers = (
        "couldn't retrieve",
        "could not retrieve",
        "no value returned",
        "no value was returned",
        "not available",
        "unable to retrieve",
    )
    return any(marker in lowered for marker in denial_markers)


def _correct_reply_with_tool_data(reply: str, data) -> str:
    if not isinstance(data, dict) or data.get("type") != "market_context":
        return reply
    fred_reply = _fred_reply_from_market_context(data)
    if fred_reply and _reply_denies_available_data(reply):
        return fred_reply
    return reply


async def run_agent(
    message: str,
    history: Optional[list[dict]] = None,
    connector: Optional[MarketDataConnector] = None,
    client: Optional[AsyncOpenAI] = None,
    news_connector: Optional[NewsConnectorBase] = None,
    fred_connector = None,
    rag_connector = None,
    agent_mode: AgentMode = "workflow",
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
            default_headers={"X-Consumer-Service": "ai-market-studio"},
            http_client=httpx.AsyncClient(trust_env=False),
        )

    messages: list[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": WORKFLOW_SYSTEM_PROMPT,
        },
    ]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message})

    last_tool_used: Optional[str] = None
    last_tool_data = None
    tool_definitions = get_tool_definitions(agent_mode)
    max_rounds = settings.agent_workflow_max_rounds

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
            for _ in range(max_rounds):
                logger.info(
                    "[Agent] mode=%s model=%s ai_path=gateway",
                    agent_mode,
                    settings.openai_model,
                )
                response = await client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    tools=tool_definitions,
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
                        logger.info(
                            "Tool call: mode=%s tool=%s tool_path=local_connector args=%s",
                            agent_mode,
                            tool_name,
                            tool_args,
                        )

                        try:
                            result = await dispatch_tool(tool_name, tool_args, connector, news_connector, fred_connector, rag_connector)
                            last_tool_used = tool_name
                            last_tool_data = result
                            # For structured UI payloads, send GPT-4o a compact summary
                            # instead of the full JSON so it doesn't echo the raw payload.
                            if isinstance(result, dict) and result.get("type") in ("insight", "market_context", "market_analysis", "market_briefing", "dashboard", "news", "rag"):
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
                reply = _correct_reply_with_tool_data(reply, last_tool_data)
                # Set accumulated totals before exiting context
                tracker.prompt_tokens = total_prompt_tokens
                tracker.completion_tokens = total_completion_tokens
                return {"reply": reply, "data": last_tool_data, "tool_used": last_tool_used}

            # Max rounds reached - set totals before exiting
            tracker.prompt_tokens = total_prompt_tokens
            tracker.completion_tokens = total_completion_tokens
    else:
        # No observability - run agent normally
        for _ in range(max_rounds):
            logger.info(
                "[Agent] mode=%s model=%s ai_path=gateway",
                agent_mode,
                settings.openai_model,
            )
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=tool_definitions,
                tool_choice="auto",
            )

            choice = response.choices[0]
            msg = choice.message
            messages.append(msg.model_dump(exclude_unset=True))

            if choice.finish_reason == "tool_calls" and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    logger.info(
                        "Tool call: mode=%s tool=%s tool_path=local_connector args=%s",
                        agent_mode,
                        tool_name,
                        tool_args,
                    )

                    try:
                        result = await dispatch_tool(tool_name, tool_args, connector, news_connector, fred_connector, rag_connector)
                        last_tool_used = tool_name
                        last_tool_data = result
                        # For structured UI payloads, send GPT-4o a compact summary
                        # instead of the full JSON so it doesn't echo the raw payload.
                        if isinstance(result, dict) and result.get("type") in ("insight", "market_context", "market_analysis", "market_briefing", "dashboard", "news", "rag"):
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
            reply = _correct_reply_with_tool_data(reply, last_tool_data)
            return {"reply": reply, "data": last_tool_data, "tool_used": last_tool_used}

    return {
        "reply": _fallback_reply_from_tool_data(last_tool_data),
        "data": last_tool_data,
        "tool_used": last_tool_used,
    }
