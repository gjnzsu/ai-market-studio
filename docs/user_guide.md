# AI Market Studio — User Guide & Developer Guide

> Version: 1.0 (PoC)
> Date: 2026-03-25
> Status: Final

---

## Part 1 — User Guide

### 1. What is AI Market Studio?

AI Market Studio is an AI-powered foreign exchange (FX) market data chatbot that lets traders, analysts, and financial professionals query live and historical exchange rates through plain-language conversation — no SQL, no dashboards, no manual lookups. You type a question such as "What is EUR/USD right now?" or "What was GBP/JPY on 1 March 2026?" and the system retrieves real data from a live market source, reasons over it with a GPT-4o AI agent, and replies in clear English. The PoC is scoped to FX spot rates from a single data source (exchangerate.host) and is intended as a clean, handoff-ready reference implementation rather than a production system.

---

### 2. How to Start the App

#### Prerequisites

- Python 3.11 or later installed and on your `PATH`
- A modern web browser (Chrome, Firefox, Edge, Safari)
- An OpenAI API key with access to `gpt-4o`
- An exchangerate.host API key (free tier available at https://exchangerate.host)

#### Step 1 — Clone the repository

```bash
git clone <repository-url>
cd ai-market-studio
```

#### Step 2 — Create and activate a virtual environment

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

#### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

#### Step 4 — Configure environment variables

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Then open `.env` in a text editor and set the following values:

```dotenv
# Required — your OpenAI API key
OPENAI_API_KEY=sk-...

# Required — your exchangerate.host API key
EXCHANGERATE_API_KEY=your_key_here

# Optional — set to true to use the mock connector instead of live data
# USE_MOCK_CONNECTOR=false
```

> **Note:** Never commit your `.env` file to version control. It is already listed in `.gitignore`.

#### Step 5 — Start the backend server

```bash
uvicorn backend.main:app --reload
```

You should see output similar to:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

#### Step 6 — Open the frontend

Open `frontend/index.html` directly in your browser. No build step or web server is required — it is a single self-contained HTML file.

On macOS:
```bash
open frontend/index.html
```

On Windows:
```bash
start frontend/index.html
```

The chat window will load and connect to the backend at `http://127.0.0.1:8000`.

---

### 3. How to Use the Chatbot

Type your question in the input box at the bottom of the chat window and press **Enter** or click **Send**. The AI agent will retrieve the relevant exchange rate data and reply in plain English.

#### Example queries and expected responses

| Your message | Expected response (approximate) |
|---|---|
| `What is EUR/USD right now?` | "The current EUR/USD rate is 1.0823 as of 2026-03-25." |
| `What was GBP/USD on 1 March 2026?` | "The GBP/USD rate on 2026-03-01 was 1.2650." |
| `Convert 1000 USD to JPY` | "1,000 USD is approximately 149,230 JPY at the current rate of 149.23." |
| `What is EUR/JPY today?` | "The current EUR/JPY rate is approximately 161.42 as of 2026-03-25. (Note: this rate is calculated via USD triangulation.)" |
| `List the rates for USD against EUR, GBP, and JPY` | "Here are today's USD rates: EUR 0.9240, GBP 0.7905, JPY 149.23." |
| `What was AUD/CAD on 15 January 2026?` | "The AUD/CAD rate on 2026-01-15 was 0.8912. (Note: calculated via USD triangulation.)" |

#### Tips for best results

- Include the currency pair explicitly using ISO 4217 codes (EUR, USD, GBP, JPY, etc.).
- For historical queries, use unambiguous date formats such as `1 March 2026` or `2026-03-01`.
- The conversation is stateful within a session — you can ask follow-up questions such as "What about last week?" after a prior query.

---

### 4. Supported Currency Pairs and Limitations

#### Supported currencies

The exchangerate.host free tier supports the following currency codes (not exhaustive):

AED, AFN, ALL, AMD, ANG, AOA, ARS, AUD, AWG, AZN, BAM, BBD, BDT, BGN, BHD, BIF, BMD, BND, BOB, BRL, BSD, BTN, BWP, BYR, BZD, CAD, CDF, CHF, CLP, CNY, COP, CRC, CUP, CVE, CZK, DJF, DKK, DOP, DZD, EGP, ERN, ETB, **EUR**, FJD, FKP, **GBP**, GEL, GHS, GIP, GMD, GNF, GTQ, GYD, HKD, HNL, HRK, HTG, HUF, IDR, ILS, INR, IQD, IRR, ISK, JMD, **JPY**, JOD, KES, KGS, KHR, KMF, KPW, KRW, KWD, KYD, KZT, LAK, LBP, LKR, LRD, LSL, LYD, MAD, MDL, MGA, MKD, MMK, MNT, MOP, MRO, MUR, MVR, MWK, MXN, MYR, MZN, NAD, NGN, NIO, NOK, NPR, NZD, OMR, PAB, PEN, PGK, PHP, PKR, PLN, PYG, QAR, RON, RSD, RUB, RWF, SAR, SBD, SCR, SDG, SEK, SGD, SHP, SLL, SOS, SRD, STD, SVC, SYP, SZL, THB, TJS, TMT, TND, TOP, TRY, TTD, TWD, TZS, UAH, UGX, **USD**, UYU, UZS, VEF, VND, VUV, WST, XAF, XCD, XOF, XPF, YER, ZAR, ZMW, ZWL

> The above list reflects the exchangerate.host free tier. Availability may vary. If a pair is not supported, the chatbot will return a clear error message.

#### How non-USD cross-rates work

The exchangerate.host free tier uses USD as its base currency for all rate lookups. When you request a pair that does not involve USD (for example EUR/JPY or GBP/AUD), the connector automatically performs **USD triangulation**:

1. Fetch EUR/USD rate.
2. Fetch JPY/USD rate.
3. Calculate EUR/JPY = (EUR/USD) ÷ (JPY/USD).

This is transparent to you as a user — the chatbot returns the correct cross-rate — but it means two API calls are made per non-USD query, which counts against the monthly quota (see below).

#### Known limitations of the PoC

| Limitation | Detail |
|---|---|
| **Free tier quota** | The exchangerate.host free tier allows approximately **100 requests per month**. Each non-USD cross-rate query consumes 2 requests. This quota will be exhausted quickly under sustained use. Use `USE_MOCK_CONNECTOR=true` for development and testing. |
| **End-of-day rates only** | The free tier provides end-of-day (EOD) closing rates, not real-time intraday prices. Rates are typically updated once per day. |
| **Historical data** | Historical rates may not be available on the free tier for all date ranges. If a historical query fails, the chatbot will return a clear error. |
| **No streaming** | Responses are returned as a single message after processing completes. There is no token-by-token streaming in the PoC. |
| **No authentication** | The PoC has no user authentication or session management. Anyone who can reach the backend can use the chatbot. |
| **CORS open to all origins** | The backend accepts requests from any origin (`*`). This is acceptable for local development but must be locked down before any deployment. |
| **No rate limiting** | The backend does not rate-limit incoming requests. A malicious or runaway client could exhaust the upstream API quota rapidly. |
| **Single data source** | Only exchangerate.host is supported. Equities, commodities, and crypto are out of scope for this PoC. |
| **English only** | The chatbot is prompted and tested in English. Other languages may produce unpredictable results. |

---

### 5. Troubleshooting

#### The chat window shows no response / "Error contacting server"

- Confirm the backend is running: open `http://127.0.0.1:8000/health` in your browser. You should see `{"status": "ok"}`.
- Check the terminal where you ran `uvicorn` for error messages.
- Ensure your `.env` file exists and contains valid values for `OPENAI_API_KEY` and `EXCHANGERATE_API_KEY`.

#### "Rate not found" or "Unsupported pair" error in the chat

- Verify the currency codes you used are valid ISO 4217 codes (e.g. `EUR`, not `Euro` or `€`).
- The pair may not be supported by the exchangerate.host free tier. Try a major pair such as EUR/USD to confirm the connector is working.

#### "API quota exceeded" or HTTP 429 error

- Your exchangerate.host free tier has been exhausted (approximately 100 requests/month).
- Switch to the mock connector for development: set `USE_MOCK_CONNECTOR=true` in your `.env` and restart the server.
- Alternatively, upgrade to a paid exchangerate.host plan.

#### "Invalid API key" / 401 error from the data source

- Check that `EXCHANGERATE_API_KEY` in your `.env` is set correctly and has not expired.
- Log in to your exchangerate.host account to verify the key is active.

#### "OpenAI API error" / 401 or 429 from OpenAI

- Check that `OPENAI_API_KEY` in your `.env` is correct and has not been revoked.
- If you receive a 429, your OpenAI account may be rate-limited or out of credits.

#### The frontend does not connect to the backend

- The frontend is hard-coded to connect to `http://127.0.0.1:8000`. If you started the backend on a different port (e.g. `--port 8080`), update the API URL in `frontend/index.html`.
- Ensure no firewall or security software is blocking port 8000.

#### Historic rate query returns an error

- Historical rate availability depends on your exchangerate.host plan. The free tier may not support all date ranges.
- If historical queries consistently fail, this feature may need to be descoped (see GAP-05 in the product documentation).

---

## Part 2 — Developer Guide

### 1. Architecture Overview

AI Market Studio uses a strict four-layer architecture. Each layer depends only on the layer directly below it, communicates through a well-defined interface, and is independently testable.

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
│               Market Data Source (exchangerate.host)            │
└─────────────────────────────────────────────────────────────────┘
```

#### Key files

| File | Layer | Responsibility |
|---|---|---|
| `frontend/index.html` | UI | Single-file chat UI (HTML + Vanilla JS) |
| `backend/main.py` | API | App factory, middleware, router mount, connector instantiation |
| `backend/router.py` | API | `/api/chat` route, error mapping, request logging |
| `backend/models.py` | API | `ChatRequest`, `ChatResponse`, `Message` Pydantic models |
| `backend/config.py` | API | `Settings` via pydantic-settings |
| `backend/agent/agent.py` | Agent | GPT-4o function-calling loop |
| `backend/agent/tools.py` | Agent | Tool JSON schemas, dispatch function |
| `backend/connectors/base.py` | Connector | `MarketDataConnector` ABC + exception hierarchy |
| `backend/connectors/exchangerate_host.py` | Connector | Live data implementation |
| `backend/connectors/mock.py` | Connector | Deterministic mock for testing |
| `tests/unit/test_connector.py` | Tests | Connector tests with `respx` HTTP mocks |
| `tests/agent/test_agent.py` | Tests | Agent loop tests with mocked OpenAI client |
| `tests/e2e/test_chat_api.py` | Tests | E2E tests via `httpx` TestClient |
| `requirements.txt` | — | All runtime and test dependencies |
| `.env.example` | — | Environment variable template |

---

### 2. How to Add a New Data Connector

All data connectors must implement the `MarketDataConnector` abstract base class defined in `backend/connectors/base.py`.

#### Step 1 — Understand the interface

```python
# backend/connectors/base.py
class MarketDataConnector(ABC):
    @abstractmethod
    async def get_exchange_rate(
        self,
        base: str,
        target: str,
        date: Optional[str] = None,  # ISO 8601: "YYYY-MM-DD"; None = latest
    ) -> dict:
        ...

    @abstractmethod
    async def list_supported_currencies(self) -> list[str]:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...
```

The canonical return dict for `get_exchange_rate` must conform to:

```python
{
    "base":      str,          # e.g. "EUR"
    "target":    str,          # e.g. "USD"
    "rate":      float,        # e.g. 1.0823
    "date":      str,          # ISO 8601 date of the rate
    "source":    str,          # connector identifier, e.g. "exchangerate_host"
    "timestamp": str,          # ISO 8601 datetime of data retrieval (UTC)
}
```

#### Step 2 — Create the connector file

Create a new file at `backend/connectors/<your_source>.py`. Name the class descriptively.

```python
# backend/connectors/my_source.py
from datetime import datetime, timezone
from typing import Optional
import httpx
from .base import MarketDataConnector, RateFetchError, UnsupportedPairError

class MySourceConnector(MarketDataConnector):
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._base_url = "https://api.mysource.example"

    async def get_exchange_rate(
        self, base: str, target: str, date: Optional[str] = None
    ) -> dict:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{self._base_url}/rate",
                    params={"base": base, "target": target, "date": date},
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=10.0,
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RateFetchError(str(exc)) from exc
            data = resp.json()
        return {
            "base": base,
            "target": target,
            "rate": float(data["rate"]),
            "date": data["date"],
            "source": "my_source",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def list_supported_currencies(self) -> list[str]:
        # Return a static list or fetch from the API
        return ["EUR", "USD", "GBP"]  # example

    async def health_check(self) -> bool:
        try:
            await self.get_exchange_rate("EUR", "USD")
            return True
        except Exception:
            return False
```

#### Step 3 — Register the connector in the factory

Open `backend/connectors/__init__.py` (or `backend/main.py`, depending on where the factory function lives) and add a branch for your new connector:

```python
from backend.connectors.my_source import MySourceConnector

def get_connector(settings: Settings) -> MarketDataConnector:
    if settings.use_mock_connector:
        return MockConnector()
    if settings.connector == "my_source":
        return MySourceConnector(api_key=settings.my_source_api_key)
    # default
    return ExchangeRateHostConnector(api_key=settings.exchangerate_api_key)
```

#### Step 4 — Add the required environment variable

Add your new API key to `.env.example`:

```dotenv
MY_SOURCE_API_KEY=your_key_here
```

And expose it in `backend/config.py`:

```python
class Settings(BaseSettings):
    my_source_api_key: str = ""
```

#### Step 5 — Write tests

Add a test file at `tests/unit/test_my_source_connector.py`. Use `respx` to mock HTTP calls — do not make real network requests in unit tests.

```python
import respx
import httpx
import pytest
from backend.connectors.my_source import MySourceConnector

@pytest.mark.asyncio
async def test_get_exchange_rate_success():
    with respx.mock:
        respx.get("https://api.mysource.example/rate").mock(
            return_value=httpx.Response(200, json={"rate": "1.08", "date": "2026-03-25"})
        )
        connector = MySourceConnector(api_key="test")
        result = await connector.get_exchange_rate("EUR", "USD")
        assert result["rate"] == 1.08
        assert result["base"] == "EUR"
```

The agent layer does not need to be modified — it depends only on the `MarketDataConnector` interface.

---

### 3. API Reference — POST /api/chat

#### Endpoint

```
POST http://127.0.0.1:8000/api/chat
Content-Type: application/json
```

#### Request body

```json
{
  "messages": [
    { "role": "user",      "content": "What is EUR/USD right now?" },
    { "role": "assistant", "content": "The current EUR/USD rate is 1.0823 as of 2026-03-25." },
    { "role": "user",      "content": "What about GBP/USD?" }
  ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `messages` | array | Yes | Full conversation history. Each element is a message object. |
| `messages[].role` | string | Yes | One of `"user"` or `"assistant"`. |
| `messages[].content` | string | Yes | The text of the message. |

The full message history must be sent on every request. The backend is stateless — it does not store conversation state between calls.

#### Response body (200 OK)

```json
{
  "reply": "The current GBP/USD rate is 1.2650 as of 2026-03-25."
}
```

| Field | Type | Description |
|---|---|---|
| `reply` | string | The AI-generated natural-language response. |

#### Error responses

| HTTP Status | Condition | Response body example |
|---|---|---|
| `400 Bad Request` | Malformed request body (e.g. missing `messages` field, wrong types) | `{"detail": "messages field is required"}` |
| `422 Unprocessable Entity` | Pydantic validation failure | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` |
| `500 Internal Server Error` | Unhandled exception in agent or connector layer | `{"detail": "Internal server error"}` |
| `502 Bad Gateway` | Upstream API (OpenAI or exchangerate.host) returned an error | `{"detail": "Upstream data source error: <message>"}` |
| `503 Service Unavailable` | Connector health check failed on startup | `{"detail": "Data connector unavailable"}` |

#### Example curl request

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is EUR/USD?"}]}'
```

#### Health check endpoint

```
GET http://127.0.0.1:8000/health
```

Returns `{"status": "ok"}` when the backend is running.

---

### 4. Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key. Must have access to `gpt-4o`. |
| `EXCHANGERATE_API_KEY` | Yes (unless using mock) | — | API key for exchangerate.host. Required even on the free tier. |
| `USE_MOCK_CONNECTOR` | No | `false` | Set to `true` to use `MockConnector` instead of the live connector. Use this for all automated tests and local development to avoid consuming API quota. |
| `OPENAI_MODEL` | No | `gpt-4o` | The OpenAI model name to use for the agent. Change only if you have access to a different model. |
| `LOG_LEVEL` | No | `INFO` | Logging level for the backend (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `CORS_ORIGINS` | No | `*` | Comma-separated list of allowed CORS origins. Default allows all origins — restrict before deployment. |
| `HOST` | No | `127.0.0.1` | Host address for uvicorn. |
| `PORT` | No | `8000` | Port for uvicorn. |

All variables are read from the `.env` file at startup via `pydantic-settings`. Environment variables set in the shell override `.env` values.

---

### 5. How to Run Tests

#### Prerequisites

Ensure you are in the project root with your virtual environment activated and dependencies installed.

For all automated tests, set `USE_MOCK_CONNECTOR=true` to avoid consuming live API quota:

```bash
export USE_MOCK_CONNECTOR=true   # macOS/Linux
# or
set USE_MOCK_CONNECTOR=true      # Windows cmd
```

Or add it to your `.env` file temporarily.

#### Run all tests

```bash
pytest
```

#### Run only unit tests

```bash
pytest tests/unit/
```

#### Run only agent tests

```bash
pytest tests/agent/
```

#### Run only E2E tests

```bash
pytest tests/e2e/
```

#### Run with verbose output

```bash
pytest -v
```

#### Run a specific test file

```bash
pytest tests/unit/test_connector.py -v
```

#### Test structure

| Test file | What it tests | Mocking strategy |
|---|---|---|
| `tests/unit/test_connector.py` | `ExchangeRateHostConnector` HTTP interactions | `respx` mocks HTTP at the transport level |
| `tests/unit/test_tools.py` | Tool JSON schema validity, dispatch function | No mocking needed (pure functions) |
| `tests/agent/test_agent.py` | GPT-4o function-calling loop logic | Mocked `openai.AsyncOpenAI` client + `MockConnector` |
| `tests/e2e/test_chat_api.py` | Full `/api/chat` request/response cycle | `httpx` TestClient + `MockConnector` |

> **Important:** Never run tests against the live exchangerate.host API. Always use `USE_MOCK_CONNECTOR=true`. The free tier quota of ~100 requests/month will be exhausted by a single test run otherwise.

---

### 6. How to Add a New Tool to the Agent Layer

The agent layer uses OpenAI function calling. Tools are defined as JSON schemas in `backend/agent/tools.py` and dispatched to the connector layer.

#### Step 1 — Define the tool schema

Open `backend/agent/tools.py` and add a new entry to the `TOOLS` list:

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_exchange_rate",
            # ... existing tool ...
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_supported_currencies",
            "description": "Returns a list of all currency codes supported by the current data connector.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]
```

The `name` field must exactly match the function name you will handle in the dispatch function.

#### Step 2 — Implement the dispatch case

In `backend/agent/tools.py`, find the `dispatch` function (or equivalent) and add a branch for your new tool:

```python
async def dispatch(tool_name: str, arguments: dict, connector: MarketDataConnector) -> dict:
    if tool_name == "get_exchange_rate":
        return await connector.get_exchange_rate(**arguments)
    elif tool_name == "list_supported_currencies":
        currencies = await connector.list_supported_currencies()
        return {"currencies": currencies}
    else:
        raise ValueError(f"Unknown tool: {tool_name}")
```

#### Step 3 — Verify the connector supports the operation

Confirm that the `MarketDataConnector` abstract base class (and all concrete implementations) have the method your tool calls. If it is a new method:

1. Add the `@abstractmethod` to `backend/connectors/base.py`.
2. Implement it in `backend/connectors/exchangerate_host.py`.
3. Implement it in `backend/connectors/mock.py` with deterministic test data.

#### Step 4 — Write tests

Add a test to `tests/unit/test_tools.py` to verify the schema is valid and the dispatch function routes correctly:

```python
import pytest
from backend.agent.tools import TOOLS, dispatch
from backend.connectors.mock import MockConnector

def test_list_supported_currencies_schema():
    names = [t["function"]["name"] for t in TOOLS]
    assert "list_supported_currencies" in names

@pytest.mark.asyncio
async def test_dispatch_list_supported_currencies():
    connector = MockConnector()
    result = await dispatch("list_supported_currencies", {}, connector)
    assert "currencies" in result
    assert isinstance(result["currencies"], list)
```

Add an agent-level test to `tests/agent/test_agent.py` to verify the agent calls the tool correctly when the user asks for supported currencies.

---

### 7. Contradictions and Gaps Found

The following discrepancies were identified during documentation authoring:

| ID | Source | Finding |
|---|---|---|
| CONTRA-01 | `team_context.md` vs `data_design.md` | `team_context.md` states the exchangerate.host free tier requires "no API key". `data_design.md` (confirmed by Wave 1 findings) states an API key (`EXCHANGERATE_API_KEY`) **is required**. The data design document is correct. All setup steps in this guide use the API key. |
| GAP-05 | `product_documentation.md` | Historical rate availability on the exchangerate.host free tier is unconfirmed. If unavailable, US-02 (historical rate queries) must be descoped. This guide documents the feature as present but notes the caveat. |
| GAP-04 | `product_documentation.md` | The GPT-4o system prompt is not defined in the architecture or team context documents. Tone and refusal behaviour are undocumented. The agent specialist must define and publish the system prompt. |

---

*End of AI Market Studio User Guide & Developer Guide.*





