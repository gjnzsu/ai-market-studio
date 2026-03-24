import json
import logging
from typing import Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from backend.config import settings
from backend.connectors.base import MarketDataConnector, ConnectorError
from backend.agent.tools import TOOL_DEFINITIONS, dispatch_tool, AgentError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are AI Market Studio, a professional FX market data assistant.
You help traders and analysts query foreign exchange rates through natural language.

Guidelines:
- Always use the available tools to fetch live data before answering rate questions.
- Present rates clearly: "The EUR/USD rate is 1.0823 as of 2026-03-25."
- For unsupported queries (stocks, crypto, news), politely say they are out of scope.
- If a data error occurs, explain the issue clearly without exposing internal details.
- Be concise and professional. Do not add unnecessary caveats.
- Supported query types: spot rates, multi-pair comparisons, historical rates (if available), supported currency list.
""".strip()

MAX_TOOL_ROUNDS = 5


async def run_agent(
    message: str,
    history: Optional[list[dict]] = None,
    connector: Optional[MarketDataConnector] = None,
    client: Optional[AsyncOpenAI] = None,
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
        client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())

    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message})

    last_tool_used: Optional[str] = None
    last_tool_data = None

    for _ in range(MAX_TOOL_ROUNDS):
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
                    result = await dispatch_tool(tool_name, tool_args, connector)
                    last_tool_used = tool_name
                    last_tool_data = result
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
