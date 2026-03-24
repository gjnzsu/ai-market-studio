# AI Market Studio — Architecture Design

> Author: SRE/AI Architect Agent
> Date: 2026-03-25
> Status: Draft — PoC scope

---

## 1. System Overview

AI Market Studio is a Proof-of-Concept FX market data chatbot. Users ask natural-language questions about foreign exchange rates; the system retrieves live or historical data and replies in plain language.

The architecture is intentionally layered so each concern is isolated and replaceable:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Chat UI (Browser)                        │
│              frontend/index.html — HTML + Vanilla JS            │
└───────────────────────────┬─────────────────────────────────────┘
                            │  POST /api/chat  { messages: [...] }
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Backend API (FastAPI)                        │
│   main.py · router.py · models.py · config.py · middleware      │
└───────────────────────────┬─────────────────────────────────────┘
                            │  await agent.run(messages)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI Agent Layer                                │
│         agent/agent.py  ·  agent/tools.py                       │
│         GPT-4o function-calling loop (OpenAI SDK)               │
└───────────────────────────┬─────────────────────────────────────┘
                            │  await connector.get_exchange_rate(...)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Data Connector Layer                            │
│   connectors/base.py (ABC)  ·  connectors/exchangerate_host.py  │
└───────────────────────────┬─────────────────────────────────────┘
                            │  HTTPS GET
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│               Market Data Source                                 │
│               api.exchangerate.host (free tier)                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Request Lifecycle (single chat turn)

1. User submits a message; JS appends it to the local `messages` array and POSTs the full array to `POST /api/chat`.
2. FastAPI deserialises the body into `ChatRequest` (Pydantic), validates it.
3. Router calls `await agent.run(messages, connector)`.
4. Agent calls `openai.AsyncOpenAI.chat.completions.create` with tool definitions and the conversation history.
5. If GPT-4o returns `finish_reason == "tool_calls"`: agent extracts arguments, dispatches to the connector.
6. Connector calls `exchangerate.host` via `httpx.AsyncClient`, normalises response, returns a typed dict.
7. Agent appends the tool result as a `tool` role message and calls GPT-4o again for synthesis.
8. GPT-4o returns `finish_reason == "stop"` with a natural-language reply.
9. Agent returns the reply string to the router.
10. Router wraps it in `ChatResponse` and returns HTTP 200.
11. JS appends the assistant message and re-renders the chat window.

---

## 3. FastAPI Application Structure

### 3.1 Entry Point — `backend/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from backend.router import router
from backend.config import settings
import logging

logging.basicConfig(level=settings.log_level)

app = FastAPI(title="AI Market Studio", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # ["*"] for PoC local dev
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(router, prefix="/api")

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

### 3.2 Router — `backend/router.py`

- Single route: `POST /api/chat`
- Receives `ChatRequest`, calls agent, returns `ChatResponse`.
- Catches `ConnectorError` → HTTP 502 (upstream data failure).
- Catches `AgentError` → HTTP 500 (model/API failure).
- All other unhandled exceptions → HTTP 500 via FastAPI default handler.
- Logs request ID, latency, and outcome at INFO level.

### 3.3 Pydantic Models — `backend/models.py`

```python
from pydantic import BaseModel, Field
from typing import Literal

class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)

class ChatResponse(BaseModel):
    reply: str
```

### 3.4 Config — `backend/config.py`

Uses `pydantic-settings`. Reads from environment / `.env` file.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4o"
    exchangerate_host_base_url: str = "https://api.exchangerate.host"
    exchangerate_host_api_key: str  # REQUIRED — free tier now mandates access_key param
    use_mock_connector: bool = False  # Set True in test environments to protect quota
    log_level: str = "INFO"
    cors_origins: list[str] = ["*"]

    class Config:
        env_file = ".env"

settings = Settings()
```

> **UPDATED (2026-03-25):** exchangerate.host now requires `access_key` on all tiers including free. The free tier also locks the base currency to USD and limits to 100 requests/month. `EXCHANGERATE_HOST_API_KEY` is a required secret — treat it with the same care as `OPENAI_API_KEY`. Set `USE_MOCK_CONNECTOR=true` in all automated test environments to protect quota.

### 3.5 Middleware Stack (PoC)

| Middleware | Purpose |
|---|---|
| `CORSMiddleware` | Allow browser cross-origin requests from `localhost` |
| Request ID injection | Attach `X-Request-ID` header (UUID4) for log correlation |
| Structured logging | Log method, path, status, latency, request_id per request |

A lightweight request-ID middleware injects a UUID into the request state and response headers:

```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

### 3.6 Error Handling Contract

| Condition | HTTP Status | Response body |
|---|---|---|
| Invalid request body | 422 | FastAPI default validation error |
| Connector upstream failure | 502 | `{"detail": "Market data unavailable"}` |
| OpenAI API failure | 500 | `{"detail": "AI service error"}` |
| Unexpected exception | 500 | `{"detail": "Internal server error"}` |

Error details are logged server-side (with request_id). Client receives only safe, generic messages.

---

## 4. AI Agent Layer Design

### 4.1 Function-Calling Loop — `backend/agent/agent.py`

The agent is a pure async function — no class state, no framework.

```
run(messages, connector, openai_client)
  │
  ├── build_messages: prepend system prompt to conversation history
  │
  └── loop (max_iterations=5 guard):
        ├── call openai_client.chat.completions.create(tools=TOOL_DEFINITIONS)
        │
        ├── if finish_reason == "stop"  → return response content
        │
        ├── if finish_reason == "tool_calls":
        │     ├── for each tool_call:
        │     │     dispatch_tool(tool_call, connector)  → result dict
        │     │     append tool result message
        │     └── continue loop
        │
        └── if max_iterations exceeded → raise AgentError
```

Key design choices:
- `openai_client` and `connector` are injected (not created inside the function) — enables unit testing with mocks.
- `max_iterations=5` prevents infinite tool-call loops.
- Loop guard raises `AgentError` rather than returning a partial response.

### 4.2 System Prompt

```
You are a financial data assistant specialising in foreign exchange (FX) markets.
You have access to live and historical FX rate data via tools.

Rules:
- Always use the provided tools to fetch rate data. Never invent or estimate rates.
- Quote rates to 4 decimal places.
- If the user asks for a currency you cannot find, say so clearly.
- Keep responses concise and factual. Do not speculate on market movements.
- Today's date is {current_date}. Use this when the user asks for "today" or "current" rates.
```

The `{current_date}` placeholder is injected at request time from `datetime.utcnow().date().isoformat()`.

### 4.3 Tool Definitions — `backend/agent/tools.py`

Two tools are defined as JSON Schema objects passed to the OpenAI `tools` parameter.

#### Tool 1: `get_fx_rate`

```json
{
  "type": "function",
  "function": {
    "name": "get_fx_rate",
    "description": "Get the exchange rate between two currencies. Use for single pair queries.",
    "parameters": {
      "type": "object",
      "properties": {
        "base": {
          "type": "string",
          "description": "ISO 4217 base currency code, e.g. EUR"
        },
        "target": {
          "type": "string",
          "description": "ISO 4217 target currency code, e.g. USD"
        },
        "date": {
          "type": "string",
          "description": "Optional ISO 8601 date (YYYY-MM-DD) for historical rate. Omit for latest."
        }
      },
      "required": ["base", "target"]
    }
  }
}
```

#### Tool 2: `get_fx_rates_list`

```json
{
  "type": "function",
  "function": {
    "name": "get_fx_rates_list",
    "description": "Get a list of all supported currency codes.",
    "parameters": {
      "type": "object",
      "properties": {},
      "required": []
    }
  }
}
```

#### Tool Dispatch

`dispatch_tool(tool_call, connector)` maps tool names to connector methods:

```python
async def dispatch_tool(tool_call, connector) -> str:
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)
    if name == "get_fx_rate":
        result = await connector.get_exchange_rate(**args)
    elif name == "get_fx_rates_list":
        result = await connector.list_supported_currencies()
    else:
        raise AgentError(f"Unknown tool: {name}")
    return json.dumps(result)
```

### 4.4 Stateless Conversation History

Conversation history is owned entirely by the browser. The backend receives the full `messages` array on every request and does not persist any state. This is a deliberate PoC choice:
- Zero backend state = trivially horizontally scalable.
- No session management, no DB.
- Trade-off: history size grows with conversation length; for PoC this is acceptable.

---

## 5. Data Connector Layer Design

### 5.1 Abstract Base Class — `backend/connectors/base.py`

```python
from abc import ABC, abstractmethod
from typing import Optional

class MarketDataConnector(ABC):

    @abstractmethod
    async def get_exchange_rate(
        self,
        base: str,
        target: str,
        date: Optional[str] = None,
    ) -> dict:
        """Returns: {base, target, rate, date, source}"""
        ...

    @abstractmethod
    async def list_supported_currencies(self) -> list[str]:
        """Returns list of ISO 4217 currency codes."""
        ...
```

The return schema for `get_exchange_rate` is fixed:
```json
{"base": "EUR", "target": "USD", "rate": 1.0823, "date": "2026-03-25", "source": "exchangerate.host"}
```

All concrete connectors MUST produce this exact schema. The agent layer depends only on this contract.

### 5.2 Connector Registration / Selection

For the PoC, a single connector is instantiated at startup in `main.py` and injected into the router via FastAPI dependency injection:

```python
# main.py
from backend.connectors.exchangerate_host import ExchangeRateHostConnector

connector = ExchangeRateHostConnector(base_url=settings.exchangerate_host_base_url)

# router.py
from fastapi import Depends

def get_connector() -> MarketDataConnector:
    return connector  # module-level singleton

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    connector: MarketDataConnector = Depends(get_connector),
) -> ChatResponse:
    ...
```

For production, the connector could be selected by a factory based on a config value (e.g. `connector_type: str = "exchangerate_host"`).

### 5.2a Cross-Rate Calculation Strategy (resolves GAP-02)

> **UPDATED (2026-03-25):** exchangerate.host free tier locks `source` to USD. All cross-pairs must use the USD-base fallback strategy below. The `access_key` query parameter is required on every call.

The `exchangerate.host /live` endpoint accepts a `source` parameter but the **free tier restricts source to USD only**. Cross-pair queries (e.g. EUR/JPY) require USD-base cross-rate computation but still only one HTTP call.

**Free-tier strategy (mandatory):** Call `/live?access_key={key}&source=USD&currencies={base},{target}`, then compute:
```
cross_rate = quotes["USD" + target] / quotes["USD" + base]
```
For a direct USD pair (e.g. EUR/USD), the rate is `quotes["USDEUR"]` inverted or `quotes["USDUSD"]` — handle identity case explicitly.

**Paid-tier primary strategy (future):** Call `/live?access_key={key}&source={base}&currencies={target}`. The endpoint returns the rate directly for the requested base.

**Fallback (if `source` parameter unsupported for a given base):** Call `/live?source=USD`, extract both `USD/{base}` and `USD/{target}`, then compute:
```
cross_rate = USD_target / USD_base
```
This is a single HTTP call plus one Python division — no additional network round-trip.

**Historical rates:** Use `/historical?date={date}&source={base}&currencies={target}` with identical logic.

**Latency impact:** Single HTTP call (~200–800ms). No risk to the 10s p95 SLO.

### 5.3 Connector Error Handling Contract

All connectors MUST raise `ConnectorError` (a custom exception) on failure. They must NOT raise raw `httpx` exceptions or return `None`.

```python
class ConnectorError(Exception):
    """Base class — raised when the data connector cannot fulfil a request."""
    pass

class RateFetchError(ConnectorError):
    """HTTP/network failure fetching a rate (wraps httpx exceptions)."""
    pass

class UnsupportedPairError(ConnectorError):
    """The requested currency pair is not available from this connector."""
    pass

class StaleDataError(ConnectorError):
    """Upstream returned data older than acceptable freshness threshold."""
    pass
```

The router catches `ConnectorError` at the base class level → HTTP 502. Subclasses allow finer-grained logging and future per-subclass handling without router changes.

Error conditions and their subclass mapping:
- `httpx.TimeoutException` / `httpx.ConnectError` / HTTP 4xx/5xx → `RateFetchError`
- Currency pair not found / unsupported base currency → `UnsupportedPairError`
- Missing or malformed fields in upstream JSON → `RateFetchError`
- Data freshness violation → `StaleDataError`

**Connector return schema** (confirmed with data-engineer — additive fields are non-breaking):
```json
{
  "base": "EUR",
  "target": "USD",
  "rate": 1.0823,
  "date": "2026-03-25",
  "source": "exchangerate.host",
  "timestamp": "2026-03-25T10:30:00Z",
  "is_mock": false
}
```
The agent layer reads only `{base, target, rate, date, source}`. `timestamp` and `is_mock` are additive — present for observability and test assertions, ignored by the agent.

---

## 6. SLIs and SLOs (PoC)

These targets are appropriate for a local development PoC. They document intent, not production commitments.

| SLI | SLO Target | Measurement Method |
|---|---|---|
| API availability | 99% during dev sessions | Health check endpoint `/health` |
| End-to-end chat latency (p50) | < 5 seconds | Server-side request timing log |
| End-to-end chat latency (p95) | < 10 seconds | Server-side request timing log |
| Connector success rate | > 95% | Count of `ConnectorError` vs total tool calls |
| OpenAI tool-call loop iterations | ≤ 3 per request (typical) | Agent loop counter log |

**Latency budget breakdown (typical request):**

```
FastAPI routing + validation:    ~5ms
OpenAI API call 1 (tool decision): ~500–1500ms
Connector HTTP call:               ~200–800ms
OpenAI API call 2 (synthesis):     ~500–1500ms
Response serialisation:            ~2ms
─────────────────────────────────────────────
Total (p50 estimate):              ~1.2–3.8s
```

---

## 7. Observability Design

### 7.1 Logging Strategy

Python standard `logging` module. Structured log lines at INFO level for all requests.

**Log fields per request:**

```
request_id  method  path  status_code  latency_ms  error_type(if any)
```

**Log fields per agent loop iteration:**

```
request_id  iteration  finish_reason  tool_name(if any)  tool_latency_ms(if any)
```

**Log levels:**
- `DEBUG`: full message payloads (gated behind `LOG_LEVEL=DEBUG`; never log in production)
- `INFO`: request/response metadata, tool dispatch events
- `WARNING`: retryable connector failures, unexpected tool names
- `ERROR`: unhandled exceptions, OpenAI API errors, connector hard failures

### 7.2 Request Tracing

`X-Request-ID` (UUID4) is generated by `RequestIDMiddleware` and:
- Attached to every log line via a logging filter that reads `request.state.request_id`.
- Returned in the HTTP response header so clients can correlate.
- Passed to the agent and connector as a parameter for downstream log correlation.

### 7.3 Error Reporting

For the PoC, errors are logged to stdout/stderr with full tracebacks at `ERROR` level. No external error aggregator (e.g. Sentry) is wired — this is a noted gap for production readiness.

---

## 8. Deployment — Local Dev Setup

### 8.1 Prerequisites

- Python 3.11+
- `pip` or `uv`
- An OpenAI API key

### 8.2 Setup Steps

```bash
# 1. Clone / enter project
cd ai-market-studio

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

# 5. Run backend
uvicorn backend.main:app --reload --port 8000

# 6. Open frontend
# Open frontend/index.html in a browser directly (file://) or serve via:
python -m http.server 3000 --directory frontend
# Then visit http://localhost:3000
```

### 8.3 Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | YES | — | OpenAI secret key |
| `OPENAI_MODEL` | no | `gpt-4o` | Model name |
| `EXCHANGERATE_HOST_API_KEY` | YES | — | exchangerate.host API key (free tier requires this; 100 req/month, USD base only) |
| `EXCHANGERATE_HOST_BASE_URL` | no | `https://api.exchangerate.host` | Connector base URL |
| `USE_MOCK_CONNECTOR` | no | `false` | Set `true` in test environments to bypass live API and protect quota |
| `LOG_LEVEL` | no | `INFO` | Python log level |
| `CORS_ORIGINS` | no | `["*"]` | Allowed CORS origins |

### 8.4 `.env.example`

```
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o
EXCHANGERATE_HOST_API_KEY=your-exchangerate-host-key-here
USE_MOCK_CONNECTOR=false
LOG_LEVEL=INFO
```

### 8.5 Running Tests

```bash
pytest tests/ -v
```

---

## 9. Scalability Considerations (Beyond PoC)

| Concern | PoC State | Production Path |
|---|---|---|
| Stateless history | Browser holds all history; no backend state | Add server-side session store (Redis) with TTL for long conversations or multi-device support |
| Single connector | Hard-coded `ExchangeRateHostConnector` | Factory pattern with config-driven selection; add Bloomberg/Refinitiv adapters |
| No auth | Open API, no authentication | Add API key or JWT middleware; rate limit per key |
| No caching | Every request hits upstream | Cache `get_exchange_rate` responses in Redis with short TTL (e.g. 30s for live rates) |
| Single process | `uvicorn` single worker | `gunicorn` + multiple `uvicorn` workers; or containerise with Docker + Kubernetes |
| No rate limiting | Unlimited requests | Add `slowapi` middleware; respect OpenAI and exchangerate.host rate limits |
| Context window growth | Conversation grows unbounded | Implement message windowing or summarisation when `len(messages) > N` |
| No streaming | Full response before render | Use OpenAI streaming + Server-Sent Events for perceived latency improvement |
| Cost control | No token tracking | Log `usage` from OpenAI response; alert on anomalous token consumption |

---

## 10. Architectural Risks

### CRITICAL

| Risk | Description | Mitigation |
|---|---|---|
| **OpenAI API key exposure** | If `OPENAI_API_KEY` is committed to git or logged at DEBUG level, it will leak. | Enforce `.env` in `.gitignore`; never log env vars; audit log output. |
| **exchangerate.host API key exposure** | `EXCHANGERATE_HOST_API_KEY` is now required and is a secret. Same leak risk as OpenAI key. | Enforce in `.gitignore`; add to `.env.example` as placeholder only; never log. |
| **Prompt injection via user input** | A malicious user could attempt to override the system prompt through the `messages` array. | System prompt is always prepended server-side and never taken from client input. Validate `role` field (only `user`/`assistant` allowed from client). |

### HIGH

| Risk | Description | Mitigation |
|---|---|---|
| **exchangerate.host reliability** | Free tier has no SLA; downtime breaks the entire demo. | Return graceful error messages via `ConnectorError`; document alternative connectors. |
| **Unbounded conversation history** | Very long conversations will hit OpenAI context limits and increase cost. | Add a PoC-level warning when `messages` exceeds 20 items; implement windowing for production. |
| **No input validation on currency codes** | GPT-4o could pass malformed strings to the connector. | Connector validates currency codes against a known list or upstream error response. |
| **Infinite tool-call loop** | GPT-4o could theoretically keep requesting tool calls. | `max_iterations=5` guard with `AgentError` raise. |

### MEDIUM

| Risk | Description | Mitigation |
|---|---|---|
| **CORS wildcard in production** | `allow_origins=["*"]` is acceptable for local PoC only. | Restrict to known origins before any deployment beyond localhost. |
| **No HTTPS for local dev** | Browser → backend traffic is plain HTTP locally. | Acceptable for PoC; use TLS termination (nginx/caddy) for any shared deployment. |

---

## 11. File Responsibility Summary

| File | Owner | Responsibility |
|---|---|---|
| `backend/main.py` | Backend specialist | App factory, middleware, router mount, connector instantiation |
| `backend/router.py` | Backend specialist | `/api/chat` route, error mapping, request logging |
| `backend/models.py` | Backend specialist | `ChatRequest`, `ChatResponse`, `Message` Pydantic models |
| `backend/config.py` | Backend specialist | `Settings` via pydantic-settings |
| `backend/agent/agent.py` | AI Agent specialist | GPT-4o function-calling loop |
| `backend/agent/tools.py` | AI Agent specialist | Tool JSON schemas, dispatch function, `AgentError` |
| `backend/connectors/base.py` | Data Connector specialist | `MarketDataConnector` ABC, `ConnectorError` |
| `backend/connectors/exchangerate_host.py` | Data Connector specialist | `ExchangeRateHostConnector` implementation |
| `frontend/index.html` | Frontend specialist | Single-file chat UI |
| `tests/unit/test_connector.py` | QA specialist | Connector tests with `respx` mocks |
| `tests/unit/test_tools.py` | QA specialist | Tool schema and dispatch tests |
| `tests/agent/test_agent.py` | QA specialist | Agent loop tests with mocked OpenAI |
| `tests/e2e/test_chat_api.py` | QA specialist | E2E tests via `httpx` TestClient |
| `requirements.txt` | QA specialist | All runtime and test dependencies |
| `.env.example` | Backend specialist | Template for environment configuration |

---

*End of Architecture Design Document.*
