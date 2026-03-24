# QA Test Cases — AI Market Studio PoC

> Version: 1.0
> Author: QA Expert (Wave 2)
> Date: 2026-03-25
> Scope: FX market data chatbot — unit, agent, and E2E test layers

---

## Ground Rules

- **Never call live APIs in automated tests.** The exchangerate.host free tier has a strict quota. All tests MUST use `MockConnector` or `respx` HTTP mocks.
- **No live LLM calls.** All agent tests use a mocked `openai.AsyncOpenAI` client with recorded fixtures.
- **Test isolation.** Each test clears state; no shared mutable fixtures between tests.
- **Coverage target.** 90 % line coverage on `backend/app/` is the minimum gate.

---

## 1. Unit Tests

### 1.1 `backend/tests/unit/test_connector.py`

#### Setup

```python
import pytest
import respx
import httpx
from app.connectors.exchangerate_host import ExchangeRateHostConnector
from app.connectors.mock_connector import MockConnector
from app.core.errors import ConnectorError
```

All `ExchangeRateHostConnector` tests use `respx.mock` to intercept outbound HTTP — **no real network calls**.

---

#### TC-CONN-01 — Happy path: direct USD pair

| Field | Value |
|---|---|
| ID | TC-CONN-01 |
| Layer | Unit |
| Priority | P0 |

**Preconditions:** `EXCHANGERATE_HOST_API_KEY` env var set to `"test_key"`.

**Steps:**
1. Intercept `GET https://api.exchangerate.host/live` with params `access_key=test_key&currencies=GBP&source=USD`.
2. Return `200` JSON: `{"success": true, "quotes": {"USDGBP": 0.7856}}`.
3. Call `connector.get_rate("USD", "GBP")`.

**Expected:** Returns `FXRate(base="USD", quote="GBP", rate=0.7856, ...)`; no exception.

```python
@pytest.mark.asyncio
async def test_get_rate_happy_path(respx_mock):
    respx_mock.get("https://api.exchangerate.host/live").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "quotes": {"USDGBP": 0.7856},
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    result = await connector.get_rate("USD", "GBP")
    assert result.base == "USD"
    assert result.quote == "GBP"
    assert result.rate == pytest.approx(0.7856)
```

---

#### TC-CONN-02 — API error: `success: false`

| Field | Value |
|---|---|
| ID | TC-CONN-02 |
| Layer | Unit |
| Priority | P0 |

**Steps:**
1. Return `200` JSON with `{"success": false, "error": {"code": 101, "type": "invalid_access_key"}}`.
2. Call `connector.get_rate("USD", "GBP")`.

**Expected:** Raises `ConnectorError` with message containing `"invalid_access_key"` or error code `101`.

```python
@pytest.mark.asyncio
async def test_get_rate_api_error(respx_mock):
    respx_mock.get("https://api.exchangerate.host/live").mock(
        return_value=httpx.Response(200, json={
            "success": False,
            "error": {"code": 101, "type": "invalid_access_key"},
        })
    )
    connector = ExchangeRateHostConnector(api_key="bad_key")
    with pytest.raises(ConnectorError, match="invalid_access_key|101"):
        await connector.get_rate("USD", "GBP")
```

---

#### TC-CONN-03 — Unsupported currency pair

| Field | Value |
|---|---|
| ID | TC-CONN-03 |
| Layer | Unit |
| Priority | P1 |

**Steps:**
1. Return `200` JSON with `{"success": true, "quotes": {}}` (empty quotes — pair not found).
2. Call `connector.get_rate("XYZ", "ABC")`.

**Expected:** Raises `ConnectorError` with message indicating the pair is unsupported or not found.

```python
@pytest.mark.asyncio
async def test_get_rate_unsupported_pair(respx_mock):
    respx_mock.get("https://api.exchangerate.host/live").mock(
        return_value=httpx.Response(200, json={"success": True, "quotes": {}})
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    with pytest.raises(ConnectorError, match="not found|unsupported|XYZABC"):
        await connector.get_rate("XYZ", "ABC")
```

---

#### TC-CONN-04 — HTTP timeout

| Field | Value |
|---|---|
| ID | TC-CONN-04 |
| Layer | Unit |
| Priority | P1 |

**Steps:**
1. Configure `respx_mock` to raise `httpx.TimeoutException`.
2. Call `connector.get_rate("USD", "EUR")`.

**Expected:** Raises `ConnectorError` with message referencing timeout.

```python
@pytest.mark.asyncio
async def test_get_rate_timeout(respx_mock):
    respx_mock.get("https://api.exchangerate.host/live").mock(
        side_effect=httpx.TimeoutException("timed out")
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    with pytest.raises(ConnectorError, match="timeout|timed out"):
        await connector.get_rate("USD", "EUR")
```

---

#### TC-CONN-05 — Missing API key raises ConnectorError at construction or first call

| Field | Value |
|---|---|
| ID | TC-CONN-05 |
| Layer | Unit |
| Priority | P0 |

**Context:** exchangerate.host requires an API key on ALL plans including free. A missing key must fail fast, not silently produce bad data.

**Steps:**
1. Unset `EXCHANGERATE_HOST_API_KEY` env var.
2. Attempt to construct `ExchangeRateHostConnector(api_key=None)` OR call `get_rate`.

**Expected:** Raises `ConnectorError` (or `ValueError`) before any HTTP call is made.

```python
def test_missing_api_key_raises():
    with pytest.raises((ConnectorError, ValueError), match="api.?key|missing|required"):
        ExchangeRateHostConnector(api_key=None)
```

---

#### TC-CONN-06 — Cross-rate triangulation (non-USD pair)

| Field | Value |
|---|---|
| ID | TC-CONN-06 |
| Layer | Unit |
| Priority | P0 |

**Context:** exchangerate.host free tier uses USD as the fixed base. Non-USD pairs (e.g. EURGBP) require **two sequential calls**: USD/EUR and USD/GBP, then compute EUR/GBP = (USD/GBP) / (USD/EUR).

**Steps:**
1. Mock `/live?source=USD&currencies=EUR` → `{"quotes": {"USDEUR": 0.9200}}`.
2. Mock `/live?source=USD&currencies=GBP` → `{"quotes": {"USDGBP": 0.7856}}`.
3. Call `connector.get_rate("EUR", "GBP")`.

**Expected:**
- HTTP client called exactly **twice**.
- Returned rate ≈ `0.7856 / 0.9200` ≈ `0.8539` (within 0.001 tolerance).

```python
@pytest.mark.asyncio
async def test_cross_rate_triangulation(respx_mock):
    respx_mock.get("https://api.exchangerate.host/live", params={"source": "USD", "currencies": "EUR", "access_key": "test_key"}).mock(
        return_value=httpx.Response(200, json={"success": True, "quotes": {"USDEUR": 0.9200}})
    )
    respx_mock.get("https://api.exchangerate.host/live", params={"source": "USD", "currencies": "GBP", "access_key": "test_key"}).mock(
        return_value=httpx.Response(200, json={"success": True, "quotes": {"USDGBP": 0.7856}})
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    result = await connector.get_rate("EUR", "GBP")
    assert result.rate == pytest.approx(0.7856 / 0.9200, abs=0.001)
    assert respx_mock.calls.call_count == 2
```

---

#### TC-CONN-07 — MockConnector returns correct schema

| Field | Value |
|---|---|
| ID | TC-CONN-07 |
| Layer | Unit |
| Priority | P0 |

**Steps:**
1. Instantiate `MockConnector()`.
2. Call `get_rate("EUR", "USD")`.

**Expected:** Returns a `FXRate` object with `base="EUR"`, `quote="USD"`, `rate` as a positive float, `timestamp` as a valid datetime.

```python
@pytest.mark.asyncio
async def test_mock_connector_schema():
    connector = MockConnector()
    result = await connector.get_rate("EUR", "USD")
    assert result.base == "EUR"
    assert result.quote == "USD"
    assert isinstance(result.rate, float) and result.rate > 0
    assert result.timestamp is not None
```

---

#### TC-CONN-08 — MockConnector raises RateFetchError for flagged currency

| Field | Value |
|---|---|
| ID | TC-CONN-08 |
| Layer | Unit |
| Priority | P1 |

**Context:** `MockConnector(error_pairs={"EUR"})` raises `RateFetchError` when `base` or `target` matches a flagged currency code — simulating upstream API failure.

```python
@pytest.mark.asyncio
async def test_mock_connector_error_pair():
    from app.core.errors import RateFetchError
    connector = MockConnector(error_pairs={"ERR"})
    with pytest.raises(RateFetchError):
        await connector.get_exchange_rate("ERR", "USD")
```

---

#### TC-CONN-09 — Historical rate happy path (US-02)

| Field | Value |
|---|---|
| ID | TC-CONN-09 |
| Layer | Unit |
| Priority | P1 |

**Context:** `/historical` endpoint is available on the free tier (same 100 req/month quota). Returns EOD rates. Tests assert schema shape, not exact rate values.

```python
@pytest.mark.asyncio
async def test_historical_rate_happy_path(respx_mock):
    respx_mock.get("https://api.exchangerate.host/historical").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "date": "2026-03-01",
            "quotes": {"USDGBP": 0.7901},
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    result = await connector.get_exchange_rate("USD", "GBP", date="2026-03-01")
    assert result["base"] == "USD"
    assert result["quote"] == "GBP"
    assert isinstance(result["rate"], float) and result["rate"] > 0
    assert result["date"] == "2026-03-01"
```

---

#### TC-CONN-10 — MockConnector passthrough of `date` parameter

| Field | Value |
|---|---|
| ID | TC-CONN-10 |
| Layer | Unit |
| Priority | P1 |

**Context:** `MockConnector` supports `date` parameter — returns `date or _MOCK_DATE` in response. Allows agent tests for US-02 without a live HTTP call.

```python
@pytest.mark.asyncio
async def test_mock_connector_date_passthrough():
    connector = MockConnector()
    result = await connector.get_exchange_rate("USD", "GBP", date="2026-03-01")
    assert result["date"] == "2026-03-01"
    assert isinstance(result["rate"], float)
```

---

### 1.2 `backend/tests/unit/test_tools.py`

#### TC-TOOL-01 — Tool JSON schema is valid

| Field | Value |
|---|---|
| ID | TC-TOOL-01 |
| Layer | Unit |
| Priority | P0 |

**Steps:**
1. Import `TOOL_DEFINITIONS` from `app.agent.tools`.
2. For each tool definition, validate against the OpenAI function-calling schema (required keys: `type`, `function.name`, `function.parameters`).

**Expected:** All definitions pass schema validation; no `KeyError`.

```python
def test_tool_schema_valid():
    from app.agent.tools import TOOL_DEFINITIONS
    for tool in TOOL_DEFINITIONS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "parameters" in fn
        params = fn["parameters"]
        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params
```

---

#### TC-TOOL-02 — Tool dispatch routes `get_fx_rate` correctly

| Field | Value |
|---|---|
| ID | TC-TOOL-02 |
| Layer | Unit |
| Priority | P0 |

**Steps:**
1. Create a `MockConnector` instance.
2. Call `dispatch_tool(tool_name="get_fx_rate", args={"base": "USD", "quote": "EUR"}, connector=mock_connector)`.

**Expected:** Returns a dict with `rate`, `base`, `quote` keys. `MockConnector.get_rate` called once.

```python
@pytest.mark.asyncio
async def test_dispatch_get_fx_rate():
    from app.agent.tools import dispatch_tool
    connector = MockConnector()
    result = await dispatch_tool(
        tool_name="get_fx_rate",
        args={"base": "USD", "quote": "EUR"},
        connector=connector,
    )
    assert "rate" in result
    assert result["base"] == "USD"
    assert result["quote"] == "EUR"
```

---

#### TC-TOOL-03 — Unknown tool raises AgentError

| Field | Value |
|---|---|
| ID | TC-TOOL-03 |
| Layer | Unit |
| Priority | P1 |

**Steps:**
1. Call `dispatch_tool(tool_name="nonexistent_tool", args={}, connector=MockConnector())`.

**Expected:** Raises `AgentError` with message referencing the unknown tool name.

```python
@pytest.mark.asyncio
async def test_dispatch_unknown_tool_raises():
    from app.agent.tools import dispatch_tool
    from app.core.errors import AgentError
    with pytest.raises(AgentError, match="nonexistent_tool|unknown tool"):
        await dispatch_tool("nonexistent_tool", {}, MockConnector())
```

---

#### TC-TOOL-04 — `get_fx_rate` schema requires `base` and `quote`

| Field | Value |
|---|---|
| ID | TC-TOOL-04 |
| Layer | Unit |
| Priority | P1 |

**Steps:**
1. Find `get_fx_rate` in `TOOL_DEFINITIONS`.
2. Assert both `"base"` and `"quote"` are in `required`.

```python
def test_get_fx_rate_required_fields():
    from app.agent.tools import TOOL_DEFINITIONS
    tool = next(t for t in TOOL_DEFINITIONS if t["function"]["name"] == "get_fx_rate")
    required = tool["function"]["parameters"]["required"]
    assert "base" in required
    assert "quote" in required
```

---

### 1.3 `backend/tests/unit/test_schemas.py`

#### TC-SCHEMA-01 — ChatRequest valid input

| Field | Value |
|---|---|
| ID | TC-SCHEMA-01 |
| Layer | Unit |
| Priority | P0 |

```python
def test_chat_request_valid():
    from app.api.schemas import ChatRequest
    req = ChatRequest(message="What is EURUSD?", session_id="abc-123")
    assert req.message == "What is EURUSD?"
    assert req.session_id == "abc-123"
```

---

#### TC-SCHEMA-02 — ChatRequest empty message rejected

| Field | Value |
|---|---|
| ID | TC-SCHEMA-02 |
| Layer | Unit |
| Priority | P0 |

```python
def test_chat_request_empty_message():
    from app.api.schemas import ChatRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ChatRequest(message="", session_id="abc-123")
```

---

#### TC-SCHEMA-03 — ChatRequest missing required field

| Field | Value |
|---|---|
| ID | TC-SCHEMA-03 |
| Layer | Unit |
| Priority | P0 |

```python
def test_chat_request_missing_message():
    from app.api.schemas import ChatRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ChatRequest(session_id="abc-123")  # message omitted
```

---

#### TC-SCHEMA-04 — ChatResponse valid serialization

| Field | Value |
|---|---|
| ID | TC-SCHEMA-04 |
| Layer | Unit |
| Priority | P1 |

```python
def test_chat_response_valid():
    from app.api.schemas import ChatResponse
    resp = ChatResponse(reply="The EUR/USD rate is 1.0823.", session_id="abc-123")
    assert resp.reply == "The EUR/USD rate is 1.0823."
    data = resp.model_dump()
    assert "reply" in data
    assert "session_id" in data
```

---

#### TC-SCHEMA-05 — ChatRequest strips leading/trailing whitespace

| Field | Value |
|---|---|
| ID | TC-SCHEMA-05 |
| Layer | Unit |
| Priority | P2 |

```python
def test_chat_request_whitespace_only_rejected():
    from app.api.schemas import ChatRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ChatRequest(message="   ", session_id="abc-123")
```

---

## 2. Agent Tests

### 2.1 `backend/tests/agent/test_agent.py`

#### Setup and Fixtures

> **GAP NOTE:** The system prompt for the GPT-4o agent is not yet defined (GAP-04 from product_documentation.md). Agent tests must inject a placeholder system prompt until the real one is specified. Tests must NOT fail because of system prompt content — they test tool-calling behaviour only.

```python
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.agent.agent import FXAgent
from app.connectors.mock_connector import MockConnector
from app.core.errors import ConnectorError, AgentError

PLACEHOLDER_SYSTEM_PROMPT = "You are a helpful FX market data assistant."

@pytest.fixture
def mock_connector():
    return MockConnector()

@pytest.fixture
def mock_openai_client():
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock()
    return client

@pytest.fixture
def agent(mock_openai_client, mock_connector):
    return FXAgent(
        openai_client=mock_openai_client,
        connector=mock_connector,
        system_prompt=PLACEHOLDER_SYSTEM_PROMPT,
    )
```

---

#### TC-AGENT-01 — Single pair query triggers `get_fx_rate` tool call

| Field | Value |
|---|---|
| ID | TC-AGENT-01 |
| Layer | Agent |
| Priority | P0 |

**Context:** The core agent behaviour — GPT-4o decides to call the tool, the agent dispatches it, then returns a final answer.

**Fixture (recorded response):**

```python
def _make_tool_call_response(tool_name, args_dict):
    """Build a mock ChatCompletion response with a single tool call."""
    tool_call = MagicMock()
    tool_call.id = "call_001"
    tool_call.function.name = tool_name
    tool_call.function.arguments = json.dumps(args_dict)
    choice = MagicMock()
    choice.finish_reason = "tool_calls"
    choice.message.tool_calls = [tool_call]
    choice.message.content = None
    response = MagicMock()
    response.choices = [choice]
    return response

def _make_final_response(content):
    """Build a mock ChatCompletion response with a plain text answer."""
    choice = MagicMock()
    choice.finish_reason = "stop"
    choice.message.tool_calls = None
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response
```

**Test:**

```python
@pytest.mark.asyncio
async def test_single_pair_calls_get_fx_rate(agent, mock_openai_client):
    mock_openai_client.chat.completions.create.side_effect = [
        _make_tool_call_response("get_fx_rate", {"base": "EUR", "quote": "USD"}),
        _make_final_response("The EUR/USD rate is 1.0823."),
    ]
    result = await agent.run([{"role": "user", "content": "What is EURUSD?"}])
    assert "EUR" in result or "1.08" in result
    # Verify tool was dispatched
    assert mock_openai_client.chat.completions.create.call_count == 2
```

---

#### TC-AGENT-02 — Multi-pair query calls connector twice

| Field | Value |
|---|---|
| ID | TC-AGENT-02 |
| Layer | Agent |
| Priority | P0 |

**Context:** User asks for two pairs. GPT-4o should call `get_fx_rate` twice in separate turns (or parallel tool calls depending on implementation).

```python
@pytest.mark.asyncio
async def test_multi_pair_calls_connector_twice(mock_openai_client, mock_connector):
    call_count = 0
    original_get = mock_connector.get_exchange_rate
    async def counting_get(base, target, date=None):
        nonlocal call_count
        call_count += 1
        return await original_get(base, target, date)
    mock_connector.get_exchange_rate = counting_get

    agent = FXAgent(
        openai_client=mock_openai_client,
        connector=mock_connector,
        system_prompt=PLACEHOLDER_SYSTEM_PROMPT,
    )
    mock_openai_client.chat.completions.create.side_effect = [
        _make_tool_call_response("get_fx_rate", {"base": "EUR", "quote": "USD"}),
        _make_tool_call_response("get_fx_rate", {"base": "GBP", "quote": "USD"}),
        _make_final_response("EUR/USD is 1.08, GBP/USD is 1.27."),
    ]
    result = await agent.run([{"role": "user", "content": "What are EUR/USD and GBP/USD?"}])
    assert call_count == 2
    assert result is not None
```

---

#### TC-AGENT-03 — ConnectorError is handled gracefully

| Field | Value |
|---|---|
| ID | TC-AGENT-03 |
| Layer | Agent |
| Priority | P0 |

**Context:** The connector raises `ConnectorError`. The agent must NOT propagate a raw exception to the API layer — it should either return an error message or raise `AgentError`.

```python
@pytest.mark.asyncio
async def test_connector_error_handled(agent, mock_openai_client, mock_connector):
    mock_connector.get_exchange_rate = AsyncMock(
        side_effect=ConnectorError("upstream failure")
    )
    mock_openai_client.chat.completions.create.side_effect = [
        _make_tool_call_response("get_fx_rate", {"base": "EUR", "quote": "USD"}),
        _make_final_response("Sorry, I could not retrieve the rate due to a data error."),
    ]
    # Should not raise — agent must handle ConnectorError and feed error message back to LLM
    result = await agent.run([{"role": "user", "content": "What is EURUSD?"}])
    assert result is not None  # graceful response, not exception
```

---

#### TC-AGENT-04 — GPT-4o returns direct answer (no tool call)

| Field | Value |
|---|---|
| ID | TC-AGENT-04 |
| Layer | Agent |
| Priority | P1 |

**Context:** GPT-4o may decide to answer without calling a tool (e.g. a greeting or meta-question). The agent must handle `finish_reason == "stop"` on the first call.

```python
@pytest.mark.asyncio
async def test_direct_answer_no_tool_call(agent, mock_openai_client):
    mock_openai_client.chat.completions.create.return_value = \
        _make_final_response("Hello! I can help with FX rates. What would you like to know?")
    result = await agent.run([{"role": "user", "content": "Hello!"}])
    assert "Hello" in result or "FX" in result
    assert mock_openai_client.chat.completions.create.call_count == 1
```

---

#### TC-AGENT-05 — Agent loop does not make unbounded tool calls

| Field | Value |
|---|---|
| ID | TC-AGENT-05 |
| Layer | Agent |
| Priority | P1 |

**Context:** Guard against an infinite loop if GPT-4o keeps returning tool calls.

```python
@pytest.mark.asyncio
async def test_agent_loop_max_iterations(agent, mock_openai_client):
    # Always return a tool call — agent must stop after max_iterations
    mock_openai_client.chat.completions.create.return_value = \
        _make_tool_call_response("get_fx_rate", {"base": "EUR", "quote": "USD"})
    with pytest.raises((AgentError, RecursionError, StopIteration)):
        await agent.run([{"role": "user", "content": "What is EURUSD?"}])
    # Alternatively assert call count is capped at a reasonable number
    assert mock_openai_client.chat.completions.create.call_count <= 10
```

---

## 3. E2E Tests

### 3.1 `backend/tests/e2e/test_chat_api.py`

#### Setup

```python
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.connectors.mock_connector import MockConnector

@pytest.fixture(scope="module")
def client():
    """Create TestClient with MockConnector injected — no live API calls."""
    app = create_app(connector=MockConnector())
    return TestClient(app)
```

---

#### TC-E2E-01 — POST /api/chat happy path

| Field | Value |
|---|---|
| ID | TC-E2E-01 |
| Layer | E2E |
| Priority | P0 |

```python
def test_chat_happy_path(client):
    response = client.post("/api/chat", json={
        "message": "What is EUR/USD?",
        "session_id": "test-session-01",
    })
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert isinstance(data["reply"], str)
    assert len(data["reply"]) > 0
```

---

#### TC-E2E-02 — Empty message returns 422 Unprocessable Entity

| Field | Value |
|---|---|
| ID | TC-E2E-02 |
| Layer | E2E |
| Priority | P0 |

```python
def test_empty_message_returns_422(client):
    response = client.post("/api/chat", json={
        "message": "",
        "session_id": "test-session-02",
    })
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
```

---

#### TC-E2E-03 — Missing `message` field returns 422

| Field | Value |
|---|---|
| ID | TC-E2E-03 |
| Layer | E2E |
| Priority | P0 |

```python
def test_missing_message_field_returns_422(client):
    response = client.post("/api/chat", json={"session_id": "test-session-03"})
    assert response.status_code == 422
```

---

#### TC-E2E-04 — Connector failure returns 503 with error message

| Field | Value |
|---|---|
| ID | TC-E2E-04 |
| Layer | E2E |
| Priority | P0 |

```python
def test_connector_failure_returns_503(monkeypatch):
    from unittest.mock import AsyncMock
    from app.core.errors import ConnectorError
    error_connector = MockConnector(error_pairs=["EUR"])
    app = create_app(connector=error_connector)
    test_client = TestClient(app, raise_server_exceptions=False)
    response = test_client.post("/api/chat", json={
        "message": "What is EUR/USD?",
        "session_id": "test-session-04",
    })
    assert response.status_code == 503
    data = response.json()
    assert "detail" in data or "error" in data
```

---

#### TC-E2E-05 — CORS headers present on OPTIONS preflight

| Field | Value |
|---|---|
| ID | TC-E2E-05 |
| Layer | E2E |
| Priority | P1 |

```python
def test_cors_headers_present(client):
    response = client.options("/api/chat", headers={
        "Origin": "http://localhost:5500",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    })
    assert response.status_code in (200, 204)
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers
```

---

#### TC-E2E-06 — Response time under 10 seconds (NFR-01)

| Field | Value |
|---|---|
| ID | TC-E2E-06 |
| Layer | E2E |
| Priority | P2 |

```python
import time

def test_response_time_under_10s(client):
    start = time.monotonic()
    response = client.post("/api/chat", json={
        "message": "What is GBP/USD?",
        "session_id": "test-session-06",
    })
    elapsed = time.monotonic() - start
    assert response.status_code == 200
    assert elapsed < 10.0, f"Response took {elapsed:.2f}s — exceeds 10s NFR"
```

---

#### TC-E2E-07 — Malformed JSON body returns 422

| Field | Value |
|---|---|
| ID | TC-E2E-07 |
| Layer | E2E |
| Priority | P1 |

```python
def test_malformed_json_returns_422(client):
    response = client.post(
        "/api/chat",
        content=b"{not valid json}",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
```

---

## 4. Test Infrastructure

### 4.1 `conftest.py` (root-level)

```python
import pytest
from app.connectors.mock_connector import MockConnector

@pytest.fixture(scope="session")
def mock_connector():
    return MockConnector()

@pytest.fixture(autouse=True)
def no_real_http(respx_mock):
    """Automatically intercept any real HTTP calls in unit tests."""
    yield
    # respx_mock will raise if unexpected calls were made
```

### 4.2 pytest configuration (`pyproject.toml` or `pytest.ini`)

```ini
[pytest]
asyncio_mode = auto
testpaths = backend/tests
env =
    USE_MOCK_CONNECTOR=true
    EXCHANGERATE_HOST_API_KEY=test_key_do_not_use
    OPENAI_API_KEY=sk-test_do_not_use
```

### 4.3 Coverage gate

```ini
[coverage:run]
source = backend/app
omit = */tests/*

[coverage:report]
fail_under = 90
```

---

## 5. Test Matrix Summary

| ID | Name | Layer | Priority | Connector | LLM |
|---|---|---|---|---|---|
| TC-CONN-01 | Happy path USD pair | Unit | P0 | respx mock | None |
| TC-CONN-02 | API error success:false | Unit | P0 | respx mock | None |
| TC-CONN-03 | Unsupported pair | Unit | P1 | respx mock | None |
| TC-CONN-04 | HTTP timeout | Unit | P1 | respx mock | None |
| TC-CONN-05 | Missing API key | Unit | P0 | respx mock | None |
| TC-CONN-06 | Cross-rate triangulation | Unit | P0 | respx mock | None |
| TC-CONN-07 | MockConnector schema | Unit | P0 | MockConnector | None |
| TC-CONN-08 | MockConnector RateFetchError injection | Unit | P1 | MockConnector | None |
| TC-CONN-09 | Historical rate happy path | Unit | P1 | respx mock | None |
| TC-CONN-10 | MockConnector date passthrough | Unit | P1 | MockConnector | None |
| TC-TOOL-01 | Tool JSON schema valid | Unit | P0 | None | None |
| TC-TOOL-02 | Dispatch routes get_fx_rate | Unit | P0 | MockConnector | None |
| TC-TOOL-03 | Unknown tool raises AgentError | Unit | P1 | MockConnector | None |
| TC-TOOL-04 | get_fx_rate required fields | Unit | P1 | None | None |
| TC-SCHEMA-01 | ChatRequest valid | Unit | P0 | None | None |
| TC-SCHEMA-02 | ChatRequest empty message | Unit | P0 | None | None |
| TC-SCHEMA-03 | ChatRequest missing field | Unit | P0 | None | None |
| TC-SCHEMA-04 | ChatResponse valid | Unit | P1 | None | None |
| TC-SCHEMA-05 | ChatRequest whitespace-only | Unit | P2 | None | None |
| TC-AGENT-01 | Single pair calls tool | Agent | P0 | MockConnector | Mocked |
| TC-AGENT-02 | Multi-pair calls connector twice | Agent | P0 | MockConnector | Mocked |
| TC-AGENT-03 | ConnectorError handled gracefully | Agent | P0 | MockConnector | Mocked |
| TC-AGENT-04 | Direct answer no tool call | Agent | P1 | MockConnector | Mocked |
| TC-AGENT-05 | Loop max iterations guard | Agent | P1 | MockConnector | Mocked |
| TC-E2E-01 | POST /api/chat happy path | E2E | P0 | MockConnector | Mocked |
| TC-E2E-02 | Empty message returns 422 | E2E | P0 | MockConnector | Mocked |
| TC-E2E-03 | Missing field returns 422 | E2E | P0 | MockConnector | Mocked |
| TC-E2E-04 | Connector failure returns 503 | E2E | P0 | MockConnector | Mocked |
| TC-E2E-05 | CORS headers present | E2E | P1 | MockConnector | Mocked |
| TC-E2E-06 | Response time under 10s | E2E | P2 | MockConnector | Mocked |
| TC-E2E-07 | Malformed JSON returns 422 | E2E | P1 | MockConnector | Mocked |

---

## 6. Gaps and Open Issues

| ID | Gap | Impact | Action |
|---|---|---|---|
| GAP-TEST-01 | System prompt for GPT-4o not yet defined (GAP-04 from product docs). Agent tests use a placeholder. | Medium — agent tone and refusal behaviour untested | Agent specialist must define and document system prompt; QA to add tone/refusal tests in Wave 3. |
| GAP-TEST-02 | ~~Historical rate endpoint availability on free tier unconfirmed.~~ **CLOSED.** `/historical` endpoint confirmed available on free tier (EOD rates, same 100 req/month quota). TC-CONN-09 and TC-CONN-10 added. Tests assert schema shape, not exact rate values. | Resolved | — |
| GAP-TEST-03 | ~~`MockConnector` error_pairs injection API not yet specified.~~ **CLOSED.** `MockConnector(error_pairs={"EUR"})` raises `RateFetchError`; `fail_pairs` raises `UnsupportedPairError`. TC-CONN-08 and TC-E2E-04 updated to use confirmed API. | Resolved | — |
| GAP-TEST-04 | No load or stress tests. Free tier quota (100 req/month) means load testing must use MockConnector only. | Low for PoC | Out of scope for PoC; note in backlog. |

---

*End of QA Test Cases document.*