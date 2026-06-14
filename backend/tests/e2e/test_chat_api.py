import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.connectors.base import RateFetchError
from backend.connectors.mcp_market_data import MCPMarketDataConnector


class FakeMCPClient:
    def __init__(self, responses=None, error=None):
        self.responses = responses or {}
        self.error = error

    async def call_tool(self, name, arguments):
        if self.error:
            raise self.error
        return self.responses[name]


def make_tool_call(name: str, args: dict, call_id: str = "call_chat_001"):
    tool_call = MagicMock()
    tool_call.id = call_id
    tool_call.function.name = name
    tool_call.function.arguments = json.dumps(args)
    return tool_call


def make_response(content=None, tool_calls=None, finish_reason=None):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    msg.model_dump.return_value = {
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
    choice.message = msg
    choice.finish_reason = finish_reason or ("tool_calls" if tool_calls else "stop")
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


def test_chat_rejects_removed_agent_mode(app_client):
    resp = app_client.post(
        "/api/chat",
        json={"message": "Brief EUR/USD", "agent_mode": "workflow"},
    )

    assert resp.status_code == 422


def test_chat_uses_single_agent_runtime(app_client, monkeypatch):
    captured = {}

    async def fake_run_agent(**kwargs):
        captured.update(kwargs)
        return {"reply": "ok", "data": None, "tool_used": None}

    monkeypatch.setattr("backend.router.run_agent", fake_run_agent)

    resp = app_client.post("/api/chat", json={"message": "What is EUR/USD?"})

    assert resp.status_code == 200
    assert "agent_mode" not in captured
    assert set(resp.json().keys()) == {"reply", "data", "tool_used"}


def test_chat_keeps_response_shape(app_client, monkeypatch):
    async def fake_run_agent(**kwargs):
        return {
            "reply": "workflow ok",
            "data": {"type": "market_briefing"},
            "tool_used": "generate_market_briefing",
        }

    monkeypatch.setattr("backend.router.run_agent", fake_run_agent)

    resp = app_client.post(
        "/api/chat",
        json={"message": "Brief EUR/USD"},
    )

    assert resp.status_code == 200
    assert set(resp.json().keys()) == {"reply", "data", "tool_used"}


def test_chat_returns_fx_analysis_workflow_data(app_client, monkeypatch):
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
    final_response = make_response(
        content="EUR/USD FX analysis ready.",
        finish_reason="stop",
    )
    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(
        side_effect=[tool_response, final_response]
    )
    monkeypatch.setattr("backend.agent.agent.AsyncOpenAI", lambda **kwargs: mock_openai)

    resp = app_client.post(
        "/api/chat",
        json={"message": "Analyze EURUSD over the next week"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["tool_used"] == "analyze_market_context"
    assert data["data"]["type"] == "fx_analysis"
    assert data["data"]["pair"] == "EUR/USD"
    assert data["data"]["research_only"] is True


def test_chat_returns_fx_analysis_from_mcp_market_data_provider(app_client, monkeypatch):
    app_client.app.state.connector = MCPMarketDataConnector(
        client=FakeMCPClient(
            {
                "get_fx_spot": {
                    "pair": "EUR/USD",
                    "base": "EUR",
                    "target": "USD",
                    "rate": 1.0865,
                    "date": "2026-06-14",
                    "source": "mcp-mock-market-data",
                }
            }
        )
    )
    tool_response = make_response(
        tool_calls=[
            make_tool_call(
                "analyze_market_context",
                {"pairs": ["EURUSD"], "analysis_type": "fx_analysis"},
            )
        ],
        finish_reason="tool_calls",
    )
    final_response = make_response(
        content="EUR/USD FX analysis ready.",
        finish_reason="stop",
    )
    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(
        side_effect=[tool_response, final_response]
    )
    monkeypatch.setattr("backend.agent.agent.AsyncOpenAI", lambda **kwargs: mock_openai)

    resp = app_client.post(
        "/api/chat",
        json={"message": "Analyze EURUSD with MCP market data"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["tool_used"] == "analyze_market_context"
    assert data["data"]["type"] == "fx_analysis"
    assert data["data"]["source_grounding"]["rate_sources"] == [
        "mcp-mock-market-data"
    ]


def test_chat_reports_no_data_when_mcp_market_data_provider_fails(app_client, monkeypatch):
    app_client.app.state.connector = MCPMarketDataConnector(
        client=FakeMCPClient(error=RuntimeError("mcp down"))
    )
    tool_response = make_response(
        tool_calls=[
            make_tool_call(
                "analyze_market_context",
                {"pairs": ["EURUSD"], "analysis_type": "fx_analysis"},
            )
        ],
        finish_reason="tool_calls",
    )
    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(return_value=tool_response)
    monkeypatch.setattr("backend.agent.agent.AsyncOpenAI", lambda **kwargs: mock_openai)

    resp = app_client.post(
        "/api/chat",
        json={"message": "Analyze EURUSD with MCP market data"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["tool_used"] is None
    assert data["data"] is None
    assert "mcp-mock-market-data" not in str(data).lower()


def test_chat_timeout_returns_504(app_client, monkeypatch):
    import asyncio

    monkeypatch.setattr(
        "backend.router.settings.agent_timeout_seconds",
        0.001,
    )

    async def slow_run_agent(**kwargs):
        await asyncio.sleep(0.1)
        return {"reply": "late", "data": None, "tool_used": None}

    monkeypatch.setattr("backend.router.run_agent", slow_run_agent)

    resp = app_client.post(
        "/api/chat",
        json={"message": "Brief EUR/USD"},
    )

    assert resp.status_code == 504


def test_chat_malformed_json_returns_422(app_client):
    resp = app_client.post(
        "/api/chat",
        content=b"{invalid json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422
