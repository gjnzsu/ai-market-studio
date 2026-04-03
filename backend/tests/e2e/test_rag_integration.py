import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import respx


def make_tool_call(name: str, args: dict, call_id: str = "call_rag_001"):
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


def test_chat_returns_normalized_rag_sources(app_client, monkeypatch):
    tool_response = make_response(
        tool_calls=[
            make_tool_call(
                "get_internal_research",
                {"question": "Find internal rollout notes"},
            )
        ],
        finish_reason="tool_calls",
    )
    final_response = make_response(
        content="I found one internal rollout note.",
        finish_reason="stop",
    )
    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(
        side_effect=[tool_response, final_response]
    )
    monkeypatch.setattr("backend.agent.agent.AsyncOpenAI", lambda **kwargs: mock_openai)

    rag_payload = {
        "answer": "Refer to the deployment checklist.",
        "sources": [
            {
                "document_id": "doc-789",
                "source_type": "pdf",
                "title": "Deployment Checklist",
                "score": 0.88,
            }
        ],
        "model": "gpt-4o",
    }

    with respx.mock(base_url="http://34.10.130.210") as respx_mock:
        respx_mock.post("/query").mock(return_value=httpx.Response(200, json=rag_payload))

        response = app_client.post(
            "/api/chat",
            json={"message": "Search internal research for rollout notes"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["tool_used"] == "get_internal_research"
    assert data["data"]["type"] == "rag"
    assert data["data"]["answer"] == "Refer to the deployment checklist."
    assert data["data"]["sources"][0]["name"] == "Deployment Checklist"
    assert data["data"]["sources"][0]["document_id"] == "doc-789"
