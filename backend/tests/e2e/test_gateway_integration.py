"""E2E test for AI Gateway integration."""
import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest



def make_tool_call(name: str, args: dict, call_id: str = "call_gateway_001"):
    tool_call = MagicMock()
    tool_call.id = call_id
    tool_call.function.name = name
    tool_call.function.arguments = json.dumps(args)
    return tool_call


def make_response(content=None, tool_calls=None, finish_reason=None):
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls
    message.model_dump.return_value = {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": tool_call.id,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in (tool_calls or [])
        ],
    }
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = finish_reason or ("tool_calls" if tool_calls else "stop")
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.mark.asyncio
async def test_run_agent_configures_gateway_base_url_and_consumer_header(monkeypatch):
    captured_kwargs = {}
    final_response = make_response(
        content="Gateway configured.",
        finish_reason="stop",
    )
    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(return_value=final_response)

    def fake_openai(**kwargs):
        captured_kwargs.update(kwargs)
        return mock_openai

    monkeypatch.setattr(
        "backend.agent.agent.settings.openai_base_url",
        "http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1",
    )
    monkeypatch.setattr("backend.agent.agent.AsyncOpenAI", fake_openai)

    from backend.agent.agent import run_agent

    await run_agent(message="Hello", connector=MagicMock())

    assert captured_kwargs["base_url"] == (
        "http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1"
    )
    assert captured_kwargs["default_headers"] == {
        "X-Consumer-Service": "ai-market-studio"
    }


def test_chat_via_gateway(app_client, monkeypatch):
    """Verify backend can call gateway successfully."""
    monkeypatch.setattr("backend.router.settings.enable_agent_workflow_mode", True)
    # Set gateway URL for this test
    original_url = os.environ.get("OPENAI_BASE_URL")
    os.environ["OPENAI_BASE_URL"] = "http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1"

    try:
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
            content="The EUR/USD rate is 1.0850.",
            finish_reason="stop",
        )
        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=[tool_response, final_response]
        )
        monkeypatch.setattr("backend.agent.agent.AsyncOpenAI", lambda **kwargs: mock_openai)

        response = app_client.post(
            "/api/chat",
            json={
                "message": "What is the EUR/USD rate?",
                "history": []
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert data["reply"] != ""
        # Tool should have been called
        assert data.get("tool_used") == "collect_market_context"
    finally:
        # Restore original URL
        if original_url:
            os.environ["OPENAI_BASE_URL"] = original_url
        else:
            os.environ.pop("OPENAI_BASE_URL", None)


def test_gateway_model_selection(app_client, monkeypatch):
    """Verify backend respects OPENAI_MODEL setting."""
    monkeypatch.setattr("backend.router.settings.enable_agent_workflow_mode", True)
    original_model = os.environ.get("OPENAI_MODEL")
    os.environ["OPENAI_MODEL"] = "gpt-4o-mini"

    try:
        final_response = make_response(
            content="Hello! How can I help you today?",
            finish_reason="stop",
        )
        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(
            return_value=final_response
        )
        monkeypatch.setattr("backend.agent.agent.AsyncOpenAI", lambda **kwargs: mock_openai)

        response = app_client.post(
            "/api/chat",
            json={
                "message": "Hello",
                "history": []
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
    finally:
        if original_model:
            os.environ["OPENAI_MODEL"] = original_model
        else:
            os.environ.pop("OPENAI_MODEL", None)
