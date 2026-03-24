import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.agent.agent import run_agent
from backend.connectors.mock_connector import MockConnector
from backend.connectors.base import RateFetchError


def make_tool_call(name: str, args: dict, call_id: str = "call_001"):
    """Build a mock tool call object."""
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(args)
    return tc


def make_response(content=None, tool_calls=None, finish_reason=None):
    """Build a mock OpenAI chat completion response."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    msg.model_dump.return_value = {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {"id": tc.id, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in (tool_calls or [])
        ],
    }
    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = finish_reason or ("tool_calls" if tool_calls else "stop")
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.mark.asyncio
async def test_agent_calls_get_exchange_rate_tool():
    """Agent calls get_exchange_rate when user asks for a single pair."""
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[make_tool_call("get_exchange_rate", {"base": "EUR", "target": "USD"})],
        finish_reason="tool_calls",
    )
    final_response = make_response(content="The EUR/USD rate is 1.0823.", finish_reason="stop")

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=[tool_response, final_response])

    result = await run_agent(
        message="What is EUR/USD?",
        connector=connector,
        client=mock_client,
    )
    assert "reply" in result
    assert result["tool_used"] == "get_exchange_rate"
    assert result["data"] is not None


@pytest.mark.asyncio
async def test_agent_calls_get_exchange_rates_for_multi_pair():
    """Agent calls get_exchange_rates for multi-currency comparison."""
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[make_tool_call("get_exchange_rates", {"base": "USD", "targets": ["EUR", "GBP", "JPY"]})],
        finish_reason="tool_calls",
    )
    final_response = make_response(content="USD rates: EUR 0.92, GBP 0.79, JPY 149.8.", finish_reason="stop")

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=[tool_response, final_response])

    result = await run_agent(
        message="Compare USD against EUR, GBP and JPY",
        connector=connector,
        client=mock_client,
    )
    assert result["tool_used"] == "get_exchange_rates"


@pytest.mark.asyncio
async def test_agent_handles_connector_error_gracefully():
    """Agent returns a reply even when connector raises RateFetchError."""
    connector = MockConnector(error_pairs={"EUR/USD"})
    tool_response = make_response(
        tool_calls=[make_tool_call("get_exchange_rate", {"base": "EUR", "target": "USD"})],
        finish_reason="tool_calls",
    )
    final_response = make_response(
        content="Sorry, I could not retrieve the EUR/USD rate at this time.",
        finish_reason="stop",
    )

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=[tool_response, final_response])

    result = await run_agent(
        message="What is EUR/USD?",
        connector=connector,
        client=mock_client,
    )
    assert result["reply"] != ""


@pytest.mark.asyncio
async def test_agent_direct_reply_no_tool_call():
    """Agent returns direct reply when GPT-4o answers without tool use."""
    connector = MockConnector()
    final_response = make_response(
        content="I can help you with FX rates. What pair would you like?",
        finish_reason="stop",
    )

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=final_response)

    result = await run_agent(
        message="Hello",
        connector=connector,
        client=mock_client,
    )
    assert result["reply"] != ""
    assert result["tool_used"] is None


@pytest.mark.asyncio
async def test_agent_passes_history_to_llm():
    """Agent includes conversation history in messages sent to GPT-4o."""
    connector = MockConnector()
    final_response = make_response(content="GBP/USD is 0.786.", finish_reason="stop")

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=final_response)

    history = [
        {"role": "user", "content": "What is EUR/USD?"},
        {"role": "assistant", "content": "EUR/USD is 1.08."},
    ]
    await run_agent(
        message="And GBP/USD?",
        history=history,
        connector=connector,
        client=mock_client,
    )
    call_args = mock_client.chat.completions.create.call_args
    messages_sent = call_args.kwargs["messages"]
    roles = [m["role"] for m in messages_sent]
    assert "system" in roles
    assert roles.count("user") >= 2
