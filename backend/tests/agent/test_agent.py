import json
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.agent.agent import WORKFLOW_SYSTEM_PROMPT, run_agent
from backend.connectors.fred_connector import InterestRateData
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
async def test_agent_default_uses_collect_market_context_tool():
    """Agent defaults to workflow data collection for a single pair."""
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[
            make_tool_call(
                "collect_market_context",
                {"pairs": ["EUR/USD"], "sources": ["rates"]},
            )
        ],
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
    assert result["data"]["type"] == "market_context"


@pytest.mark.asyncio
async def test_tool_call_logs_local_connector_path(caplog):
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[
            make_tool_call(
                "collect_market_context",
                {"pairs": ["EUR/USD"], "sources": ["rates"]},
            )
        ],
        finish_reason="tool_calls",
    )
    final_response = make_response(content="The EUR/USD rate is 1.0823.", finish_reason="stop")
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=[tool_response, final_response])

    with caplog.at_level(logging.INFO, logger="backend.agent.agent"):
        await run_agent(
            message="What is EUR/USD?",
            connector=connector,
            client=mock_client,
        )

    assert "tool_path=local_connector" in caplog.text


@pytest.mark.asyncio
async def test_market_context_summary_includes_fred_values_for_final_answer():
    fred_connector = AsyncMock()
    fred_connector.get_current_rate.return_value = InterestRateData(
        series_id="FEDFUNDS",
        series_name="Effective Federal Funds Rate (monthly)",
        date="2026-05-01",
        value=3.63,
        unit="percent",
        source="FRED",
    )
    tool_response = make_response(
        tool_calls=[
            make_tool_call(
                "collect_market_context",
                {"sources": ["fred"], "fred_series_ids": ["FEDFUNDS"]},
            )
        ],
        finish_reason="tool_calls",
    )
    final_response = make_response(content="The federal funds rate is 3.63%.", finish_reason="stop")
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=[tool_response, final_response])

    await run_agent(
        message="What is the current Federal Funds Rate?",
        connector=MockConnector(),
        fred_connector=fred_connector,
        client=mock_client,
    )

    second_call_messages = mock_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    tool_summary = next(
        message["content"]
        for message in second_call_messages
        if message.get("role") == "tool"
    )
    assert "FEDFUNDS" in tool_summary
    assert "3.63" in tool_summary


@pytest.mark.asyncio
async def test_agent_overrides_fred_retrieval_denial_when_tool_data_has_value():
    fred_connector = AsyncMock()
    fred_connector.get_current_rate.return_value = InterestRateData(
        series_id="FEDFUNDS",
        series_name="Effective Federal Funds Rate (monthly)",
        date="2026-05-01",
        value=3.63,
        unit="percent",
        source="FRED",
    )
    tool_response = make_response(
        tool_calls=[
            make_tool_call(
                "collect_market_context",
                {"sources": ["fred"], "fred_series_ids": ["FEDFUNDS"]},
            )
        ],
        finish_reason="tool_calls",
    )
    bad_final_response = make_response(
        content="I couldn't retrieve the Federal Funds Rate from FRED just now.",
        finish_reason="stop",
    )
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[tool_response, bad_final_response]
    )

    result = await run_agent(
        message="What is the current Federal Funds Rate?",
        connector=MockConnector(),
        fred_connector=fred_connector,
        client=mock_client,
    )

    assert "3.63" in result["reply"]
    assert "couldn't retrieve" not in result["reply"].lower()


@pytest.mark.asyncio
async def test_agent_default_uses_workflow_collection_for_multi_pair():
    """Agent uses workflow collection for multi-currency comparison."""
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[
            make_tool_call(
                "collect_market_context",
                {"pairs": ["USD/EUR", "USD/GBP", "USD/JPY"], "sources": ["rates"]},
            )
        ],
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
        tool_calls=[
            make_tool_call(
                "collect_market_context",
                {"pairs": ["EUR/USD"], "sources": ["rates"]},
            )
        ],
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
async def test_agent_default_uses_workflow_tool_set_and_system_prompt():
    connector = MockConnector()
    final_response = make_response(content="ok", finish_reason="stop")
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=final_response)

    await run_agent(
        message="Brief EUR/USD",
        connector=connector,
        client=mock_client,
    )

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    tools = call_kwargs["tools"]
    names = [tool["function"]["name"] for tool in tools]
    assert names == [
        "collect_market_context",
        "analyze_market_context",
        "generate_market_briefing",
    ]
    assert call_kwargs["messages"][0]["content"] == WORKFLOW_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_workflow_mode_can_use_market_briefing_tool_for_insight():
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
        agent_mode="workflow",
    )

    assert result["tool_used"] == "generate_market_briefing"
    assert result["data"]["type"] == "market_briefing"


@pytest.mark.asyncio
async def test_workflow_mode_can_use_market_briefing_with_explicit_playbook():
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
        agent_mode="workflow",
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
        agent_mode="workflow",
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
        agent_mode="workflow",
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
async def test_workflow_mode_unknown_tool_does_not_fallback_to_legacy():
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
        agent_mode="workflow",
    )

    assert result["tool_used"] is None


@pytest.mark.asyncio
async def test_workflow_mode_returns_structured_fallback_at_configured_step_limit(monkeypatch):
    connector = MockConnector()
    monkeypatch.setattr("backend.agent.agent.settings.agent_workflow_max_rounds", 1)
    tool_response = make_response(
        tool_calls=[
            make_tool_call(
                "analyze_market_context",
                {"pairs": ["EUR/USD"], "analysis_type": "trend", "days": 5},
            )
        ],
        finish_reason="tool_calls",
    )
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=tool_response)

    result = await run_agent(
        message="Keep working on EUR/USD until complete",
        connector=connector,
        client=mock_client,
        agent_mode="workflow",
    )

    reply = result["reply"].lower()
    assert "trend analysis" in reply
    assert "eur/usd" in reply
    assert "step limit" not in reply
    assert result["tool_used"] == "analyze_market_context"
    assert result["data"]["type"] == "market_analysis"


@pytest.mark.asyncio
async def test_previous_workflow_failure_does_not_alter_later_default_tool_set():
    connector = MockConnector()
    workflow_tool_response = make_response(
        tool_calls=[make_tool_call("unknown_workflow_tool", {})],
        finish_reason="tool_calls",
    )
    workflow_final_response = make_response(content="Workflow failed.", finish_reason="stop")
    next_final_response = make_response(content="Workflow ok.", finish_reason="stop")
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[workflow_tool_response, workflow_final_response, next_final_response]
    )

    await run_agent(
        message="Brief EUR/USD",
        connector=connector,
        client=mock_client,
    )
    await run_agent(
        message="What is EUR/USD?",
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


def test_gateway_backed_mcp_tool_path_not_implemented_yet():
    pytest.skip(
        "No gateway-backed MCP tool connector is implemented in ai-market-studio yet"
    )
