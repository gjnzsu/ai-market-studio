import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.agent.agent import run_agent
from backend.connectors.mock_connector import MockConnector


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
async def test_agent_can_collect_market_context_for_single_pair():
    """Agent calls collect_market_context when user asks for a single pair."""
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[make_tool_call("collect_market_context", {"pairs": ["EUR/USD"], "sources": ["rates"]})],
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
    assert result["tool_used"] == "collect_market_context"
    assert result["data"] is not None


@pytest.mark.asyncio
async def test_agent_can_collect_market_context_for_multi_pair():
    """Agent calls collect_market_context for multi-currency comparison."""
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[make_tool_call("collect_market_context", {"pairs": ["USD/EUR", "USD/GBP", "USD/JPY"], "sources": ["rates"]})],
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
    assert result["tool_used"] == "collect_market_context"


@pytest.mark.asyncio
async def test_agent_handles_connector_error_gracefully():
    """Agent returns a reply even when connector raises RateFetchError."""
    connector = MockConnector(error_pairs={"EUR/USD"})
    tool_response = make_response(
        tool_calls=[make_tool_call("collect_market_context", {"pairs": ["EUR/USD"], "sources": ["rates"]})],
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


@pytest.mark.asyncio
async def test_agent_uses_intent_level_workflow_tool_set():
    connector = MockConnector()
    final_response = make_response(content="ok", finish_reason="stop")
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=final_response)

    await run_agent(
        message="Brief EUR/USD",
        connector=connector,
        client=mock_client,
    )

    tools = mock_client.chat.completions.create.call_args.kwargs["tools"]
    names = [tool["function"]["name"] for tool in tools]
    assert names == [
        "collect_market_context",
        "analyze_market_context",
        "generate_market_briefing",
    ]


@pytest.mark.asyncio
async def test_agent_can_use_market_briefing_tool_for_insight():
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[make_tool_call("generate_market_briefing", {"pairs": ["EUR/USD"]})],
        finish_reason="tool_calls",
    )
    final_response = make_response(content="EUR/USD briefing ready.", finish_reason="stop")
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[tool_response, final_response]
    )

    result = await run_agent(
        message="Give me a market insight on EUR/USD",
        connector=connector,
        client=mock_client,
    )

    assert result["tool_used"] == "generate_market_briefing"
    assert result["data"]["type"] == "market_briefing"


@pytest.mark.asyncio
async def test_agent_can_use_market_analysis_tool_for_fx_analysis():
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[
            make_tool_call(
                "analyze_market_context",
                {
                    "pairs": ["EURUSD"],
                    "analysis_type": "fx_analysis",
                    "horizon": "1w",
                    "focus": "ECB vs Fed",
                },
            )
        ],
        finish_reason="tool_calls",
    )
    final_response = make_response(content="EUR/USD FX analysis ready.", finish_reason="stop")
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[tool_response, final_response]
    )

    result = await run_agent(
        message="Analyze EURUSD over the next week",
        connector=connector,
        client=mock_client,
    )

    assert result["tool_used"] == "analyze_market_context"
    assert result["data"]["type"] == "fx_analysis"
    assert result["data"]["pair"] == "EUR/USD"
    assert result["data"]["horizon"] == "1w"
    assert result["data"]["research_only"] is True


@pytest.mark.asyncio
async def test_agent_can_use_market_briefing_with_explicit_playbook():
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[
            make_tool_call(
                "generate_market_briefing",
                {"pairs": ["EUR/USD"], "playbook": "fx_carry", "include_research": False},
            )
        ],
        finish_reason="tool_calls",
    )
    final_response = make_response(content="EUR/USD carry briefing ready.", finish_reason="stop")
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[tool_response, final_response]
    )

    result = await run_agent(
        message="Give me an FX carry view on EUR/USD",
        connector=connector,
        client=mock_client,
    )

    assert result["tool_used"] == "generate_market_briefing"
    assert result["data"]["playbook"]["id"] == "fx_carry"
    assert result["data"]["source_grounding"]["synthetic_sources"] == [
        "forward_curve",
        "implied_volatility",
    ]
    assert result["data"]["data_gaps"] == []
    assert result["data"]["specialist_data"]["source"] == "synthetic"
    assert result["data"]["carry_metrics"]["source"] == "synthetic"


@pytest.mark.asyncio
async def test_workflow_market_briefing_summary_includes_playbook_details():
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[
            make_tool_call(
                "generate_market_briefing",
                {"pairs": ["EUR/USD"], "playbook": "macro_rates", "include_research": False},
            )
        ],
        finish_reason="tool_calls",
    )
    final_response = make_response(content="EUR/USD macro briefing ready.", finish_reason="stop")
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[tool_response, final_response]
    )

    await run_agent(
        message="Give me a macro rates monitor for EUR/USD",
        connector=connector,
        client=mock_client,
    )

    second_call_messages = mock_client.chat.completions.create.call_args_list[1].kwargs[
        "messages"
    ]
    tool_message = next(message for message in second_call_messages if message["role"] == "tool")
    tool_summary = json.loads(tool_message["content"])

    assert tool_summary["playbook"]["id"] == "macro_rates"
    assert "data_gaps" in tool_summary
    assert "source_grounding" in tool_summary


@pytest.mark.asyncio
async def test_workflow_market_briefing_summary_includes_synthetic_carry_details():
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[
            make_tool_call(
                "generate_market_briefing",
                {"pairs": ["EUR/USD"], "playbook": "fx_carry", "include_research": False},
            )
        ],
        finish_reason="tool_calls",
    )
    final_response = make_response(content="EUR/USD carry briefing ready.", finish_reason="stop")
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[tool_response, final_response]
    )

    await run_agent(
        message="Give me an FX carry view on EUR/USD",
        connector=connector,
        client=mock_client,
    )

    second_call_messages = mock_client.chat.completions.create.call_args_list[1].kwargs[
        "messages"
    ]
    tool_message = next(message for message in second_call_messages if message["role"] == "tool")
    tool_summary = json.loads(tool_message["content"])

    assert tool_summary["source_grounding"]["synthetic_sources"] == [
        "forward_curve",
        "implied_volatility",
    ]
    assert tool_summary["specialist_data"]["source"] == "synthetic"
    assert tool_summary["carry_metrics"]["source"] == "synthetic"


@pytest.mark.asyncio
async def test_unknown_tool_does_not_fallback_to_legacy():
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[make_tool_call("unknown_workflow_tool", {})],
        finish_reason="tool_calls",
    )
    final_response = make_response(
        content="Could not complete workflow.",
        finish_reason="stop",
    )
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[tool_response, final_response]
    )

    result = await run_agent(
        message="Brief EUR/USD",
        connector=connector,
        client=mock_client,
    )

    assert result["tool_used"] is None


@pytest.mark.asyncio
async def test_agent_stops_at_configured_step_limit(monkeypatch):
    connector = MockConnector()
    monkeypatch.setattr("backend.agent.agent.settings.agent_max_rounds", 1)
    tool_response = make_response(
        tool_calls=[make_tool_call("collect_market_context", {"pairs": ["EUR/USD"]})],
        finish_reason="tool_calls",
    )
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=tool_response)

    result = await run_agent(
        message="Keep working on EUR/USD until complete",
        connector=connector,
        client=mock_client,
    )

    reply = result["reply"].lower()
    assert "too complex" in reply or "incomplete" in reply
    assert result["tool_used"] == "collect_market_context"

