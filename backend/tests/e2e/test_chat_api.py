import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.connectors.base import RateFetchError


def make_response(content=None, tool_calls=None, finish_reason=None):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    msg.model_dump.return_value = {"role": "assistant", "content": content, "tool_calls": []}
    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = finish_reason or "stop"
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.fixture
def client_with_mock_llm(app_client, monkeypatch):
    """App client with both MockConnector and mocked OpenAI client."""
    final_response = make_response(content="The EUR/USD rate is 1.0823.", finish_reason="stop")
    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(return_value=final_response)
    monkeypatch.setattr("backend.agent.agent.AsyncOpenAI", lambda **kwargs: mock_openai)
    return app_client


def test_chat_happy_path(client_with_mock_llm):
    resp = client_with_mock_llm.post("/api/chat", json={"message": "What is EUR/USD?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert isinstance(data["reply"], str)
    assert len(data["reply"]) > 0


def test_chat_empty_message_returns_422(app_client):
    resp = app_client.post("/api/chat", json={"message": ""})
    assert resp.status_code == 422


def test_chat_missing_message_returns_422(app_client):
    resp = app_client.post("/api/chat", json={})
    assert resp.status_code == 422


def test_chat_connector_failure_returns_503(app_client, monkeypatch):
    """When connector raises RateFetchError, API returns 503."""
    async def failing_run_agent(**kwargs):
        raise RateFetchError("Simulated connector failure")
    monkeypatch.setattr("backend.router.run_agent", failing_run_agent)
    resp = app_client.post("/api/chat", json={"message": "What is EUR/USD?"})
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()


def test_chat_cors_headers_present(client_with_mock_llm):
    resp = client_with_mock_llm.post(
        "/api/chat",
        json={"message": "What is EUR/USD?"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert resp.status_code == 200


def test_chat_with_history(client_with_mock_llm):
    resp = client_with_mock_llm.post("/api/chat", json={
        "message": "And GBP/USD?",
        "history": [
            {"role": "user", "content": "What is EUR/USD?"},
            {"role": "assistant", "content": "EUR/USD is 1.08."},
        ],
    })
    assert resp.status_code == 200
    assert "reply" in resp.json()


def test_chat_workflow_mode_disabled_is_rejected(app_client, monkeypatch):
    monkeypatch.setattr("backend.router.settings.enable_agent_workflow_mode", False)

    resp = app_client.post(
        "/api/chat",
        json={"message": "Brief EUR/USD", "agent_mode": "workflow"},
    )

    assert resp.is_error
    assert "workflow" in resp.text.lower()


def test_chat_default_mode_passes_legacy_to_run_agent(app_client, monkeypatch):
    captured = {}

    async def fake_run_agent(**kwargs):
        captured.update(kwargs)
        return {"reply": "ok", "data": None, "tool_used": None}

    monkeypatch.setattr("backend.router.run_agent", fake_run_agent)

    resp = app_client.post("/api/chat", json={"message": "What is EUR/USD?"})

    assert resp.status_code == 200
    assert captured["agent_mode"] == "legacy"
    assert set(resp.json().keys()) == {"reply", "data", "tool_used"}


def test_chat_explicit_legacy_mode_passes_legacy_to_run_agent(app_client, monkeypatch):
    captured = {}

    async def fake_run_agent(**kwargs):
        captured.update(kwargs)
        return {"reply": "ok", "data": None, "tool_used": None}

    monkeypatch.setattr("backend.router.run_agent", fake_run_agent)

    resp = app_client.post(
        "/api/chat",
        json={"message": "What is EUR/USD?", "agent_mode": "legacy"},
    )

    assert resp.status_code == 200
    assert captured["agent_mode"] == "legacy"
    assert set(resp.json().keys()) == {"reply", "data", "tool_used"}


def test_chat_workflow_mode_keeps_response_shape_when_enabled(app_client, monkeypatch):
    captured = {}
    monkeypatch.setattr("backend.router.settings.enable_agent_workflow_mode", True)

    async def fake_run_agent(**kwargs):
        captured.update(kwargs)
        return {
            "reply": "workflow ok",
            "data": {"type": "market_briefing"},
            "tool_used": "generate_market_briefing",
        }

    monkeypatch.setattr("backend.router.run_agent", fake_run_agent)

    resp = app_client.post(
        "/api/chat",
        json={"message": "Brief EUR/USD", "agent_mode": "workflow"},
    )

    assert resp.status_code == 200
    assert captured["agent_mode"] == "workflow"
    assert set(resp.json().keys()) == {"reply", "data", "tool_used"}


def test_chat_workflow_timeout_returns_504(app_client, monkeypatch):
    import asyncio

    monkeypatch.setattr("backend.router.settings.enable_agent_workflow_mode", True)
    monkeypatch.setattr(
        "backend.router.settings.agent_workflow_timeout_seconds",
        0.001,
    )

    async def slow_run_agent(**kwargs):
        await asyncio.sleep(0.1)
        return {"reply": "late", "data": None, "tool_used": None}

    monkeypatch.setattr("backend.router.run_agent", slow_run_agent)

    resp = app_client.post(
        "/api/chat",
        json={"message": "Brief EUR/USD", "agent_mode": "workflow"},
    )

    assert resp.status_code == 504


def test_chat_malformed_json_returns_422(app_client):
    resp = app_client.post(
        "/api/chat",
        content=b"{invalid json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422
