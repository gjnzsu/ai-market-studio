# AI Market Studio — Team Context Document

_Generated: 2026-03-26. Supersedes all previous versions. All specialist agents must read this before beginning work._

---

## 1. Project Overview

### Purpose
AI Market Studio is a proof-of-concept FX market data chatbot. Users type natural-language questions; GPT-4o interprets intent via function calling, fetches rate data from exchangerate.host, and returns a conversational answer. No agent framework — raw OpenAI function calling only.

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Single HTML file, Vanilla JS, no external libraries, no build step |
| Backend API | Python 3.11+, FastAPI 0.115, Uvicorn 0.30 |
| AI Agent | OpenAI GPT-4o, function calling |
| Data Source | exchangerate.host REST API (free tier, requires API key) |
| Config | pydantic-settings 2.5, python-dotenv 1.0 |
| HTTP client | httpx 0.27 (async) |
| Testing | pytest 8.3, respx 0.21, pytest-asyncio 0.24, pytest-cov 5.0 |

### Architecture (5 Layers)

```
Chat UI  (frontend/index.html)
    │  POST /api/chat  {message, history}
    ▼
Backend API  (backend/main.py · router.py · models.py · config.py)
    │  await run_agent(message, history, connector)
    ▼
AI Agent Layer  (backend/agent/agent.py · agent/tools.py)
    │  OpenAI tool dispatch → dispatch_tool(name, args, connector)
    ▼
Data Connector Layer  (backend/connectors/base.py · exchangerate_host.py · mock_connector.py)
    │  HTTPS GET
    ▼
Market Data Source  (https://api.exchangerate.host)
```

### Feature 01 — Delivered
- Natural-language chat for FX spot rates (live and historical)
- GPT-4o selects from 3 tools: `get_exchange_rate`, `get_exchange_rates`, `list_supported_currencies`
- Non-USD cross-rates via USD triangulation (transparent to caller)
- MockConnector with error injection for all automated tests
- 90% coverage gate, tests never hit live API

---

## 2. Key Files & Responsibilities

### Project Layout

```
ai-market-studio/
├── backend/
│   ├── main.py                        # App factory, CORS, connector instantiation, lifespan
│   ├── router.py                      # POST /api/chat endpoint
│   ├── models.py                      # ChatRequest, ChatResponse, Message (Pydantic)
│   ├── config.py                      # Settings via pydantic-settings
│   ├── agent/
│   │   ├── agent.py                   # run_agent() — GPT-4o function-calling loop
│   │   └── tools.py                   # TOOL_DEFINITIONS, dispatch_tool(), AgentError
│   ├── connectors/
│   │   ├── base.py                    # MarketDataConnector ABC + error hierarchy
│   │   ├── exchangerate_host.py       # ExchangeRateHostConnector (live API)
│   │   └── mock_connector.py          # MockConnector (deterministic, error injection)
│   └── tests/
│       ├── conftest.py                # Shared fixtures (app_client with MockConnector)
│       ├── unit/
│       │   ├── test_connector.py      # Connector unit tests (respx HTTP mocks)
│       │   ├── test_tools.py          # Tool schema and dispatch tests
│       │   └── test_schemas.py        # Pydantic model tests
│       ├── agent/
│       │   └── test_agent.py          # Agent loop tests (mocked OpenAI client)
│       └── e2e/
│           └── test_chat_api.py       # FastAPI TestClient + MockConnector
├── frontend/
│   └── index.html                     # Single-file chat UI
├── docs/                              # All design documents
├── requirements.txt                   # Runtime + test dependencies
├── .env.example                       # Env var template
└── .env                               # Local secrets (git-ignored)
```

### `backend/main.py`
App factory `create_app()`. Reads `USE_MOCK_CONNECTOR` from settings to choose connector at startup. Mounts frontend static files at `/`. CORS configured via `CORS_ORIGINS` env var.

```python
def create_connector():
    if settings.use_mock_connector:
        return MockConnector()
    return ExchangeRateHostConnector(api_key=settings.exchangerate_api_key.get_secret_value())

@asynccontextmanager
async def lifespan(app):
    app.state.connector = create_connector()
    yield
```

### `backend/router.py`
Single endpoint. Pulls connector from `app.state`. Maps `ConnectorError` → 503, all other exceptions → 500.

```python
@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    connector = request.app.state.connector
    result = await run_agent(message=body.message, history=[m.model_dump() for m in body.history], connector=connector)
    return ChatResponse(reply=result["reply"], data=result["data"], tool_used=result["tool_used"])
```

### `backend/models.py`

```python
class Message(BaseModel):
    role: str       # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str    # validated non-empty
    history: list[Message] = []

class ChatResponse(BaseModel):
    reply: str
    data: Optional[Any] = None      # raw connector result dict / list
    tool_used: Optional[str] = None # e.g. "get_exchange_rate"
```

_Feature 02 gap: no structured schema for chart/dashboard data yet._

### `backend/config.py`

```python
class Settings(BaseSettings):
    openai_api_key: SecretStr
    openai_model: str = "gpt-4o"
    exchangerate_api_key: SecretStr   # REQUIRED — free tier needs key
    use_mock_connector: bool = False  # Set True in CI
    cors_origins: str = "*"           # Comma-separated; lock down for prod
```

### `backend/agent/agent.py`
`run_agent(message, history, connector, client)` — the GPT-4o loop. Accepts injectable `client` for testing. System prompt is defined here. Loops up to `MAX_TOOL_ROUNDS = 5`. Returns `{reply, data, tool_used}`.

### `backend/agent/tools.py`
Defines `TOOL_DEFINITIONS` (3 tools sent to GPT-4o) and `dispatch_tool(name, args, connector)`.

**Tool definitions:**

```python
TOOL_DEFINITIONS = [
    {
        "name": "get_exchange_rate",
        "description": "Get the exchange rate for a single currency pair. Use when user asks about one specific pair.",
        "parameters": {
            "required": ["base", "target"],
            "properties": {
                "base":   {"type": "string"},  # ISO 4217, e.g. "EUR"
                "target": {"type": "string"},  # ISO 4217, e.g. "USD"
                "date":   {"type": "string"},  # YYYY-MM-DD, optional — omit for latest
            }
        }
    },
    {
        "name": "get_exchange_rates",
        "description": "Get rates for multiple target currencies from one base. Use for comparisons.",
        "parameters": {
            "required": ["base", "targets"],
            "properties": {
                "base":    {"type": "string"},
                "targets": {"type": "array", "items": {"type": "string"}},
                "date":    {"type": "string"},  # optional
            }
        }
    },
    {
        "name": "list_supported_currencies",
        "description": "Return the list of supported ISO 4217 currency codes.",
        "parameters": {"required": [], "properties": {}}
    }
]
```

### `backend/connectors/base.py`
Abstract interface and error hierarchy:

```python
class ConnectorError(Exception): ...
class RateFetchError(ConnectorError): ...    # HTTP errors, timeouts, parse failures
class UnsupportedPairError(ConnectorError): ... # pair not available
class StaleDataError(ConnectorError): ...    # reserved for real-time sources

class MarketDataConnector(ABC):
    async def get_exchange_rate(self, base: str, target: str, date: Optional[str] = None) -> dict: ...
    async def get_exchange_rates(self, base: str, targets: list[str], date: Optional[str] = None) -> list[dict]: ...
    async def list_supported_currencies(self) -> list[str]: ...
```

**Canonical rate dict** (returned by all connector methods):
```python
{"base": "EUR", "target": "USD", "rate": 1.0823, "date": "2026-03-26", "source": "exchangerate.host"}
```

### `backend/connectors/exchangerate_host.py`

- **Live rates**: `GET /live?access_key=...&source=USD&currencies=EUR,GBP`
- **Historical rates**: `GET /historical?date=YYYY-MM-DD&access_key=...&source=USD&currencies=...`
- **USD base lock**: free tier only supports USD as base. Non-USD cross-rates use triangulation:
  - Fetch both `USDBASE` and `USDTARGET` in one call
  - Compute `base→target = USDTARGET / USDBASE`
- **Quota**: ~100 requests/month on free tier
- Raises `RateFetchError` on HTTP errors, API `success:false`, or missing quotes
- Raises `UnsupportedPairError` if a currency is absent from the response

```python
class ExchangeRateHostConnector(MarketDataConnector):
    def __init__(self, api_key: str) -> None: ...
    async def _fetch_usd_rates(self, currencies: list[str], date: Optional[str]) -> dict: ...
    async def get_exchange_rate(self, base, target, date=None) -> dict: ...
    async def get_exchange_rates(self, base, targets, date=None) -> list[dict]: ...
    async def list_supported_currencies(self) -> list[str]: ...
```

### `backend/connectors/mock_connector.py`
Deterministic test connector. Never hits the network.

```python
DEFAULT_RATES = {"USDEUR": 0.9201, "USDGBP": 0.7856, "USDJPY": 149.82, ...}  # 10 pairs
SUPPORTED_CURRENCIES = ["USD","EUR","GBP","JPY","AUD","CAD","CHF","CNY","HKD","SGD","NZD"]

class MockConnector(MarketDataConnector):
    def __init__(
        self,
        overrides: Optional[dict[str, float]] = None,   # e.g. {"USDEUR": 1.05}
        error_pairs: Optional[set[str]] = None,          # e.g. {"EUR/USD"} → RateFetchError
        unsupported_pairs: Optional[set[str]] = None,    # e.g. {"EUR/XYZ"} → UnsupportedPairError
    ): ...
```

**Key limitation for Feature 02**: `date` parameter is accepted but **ignored** — all dates return the same static rates. For historical trend testing, MockConnector must be extended to generate per-date variation.

### `frontend/index.html`
Single-file chat UI. Dark theme (`#0f1117` bg). Key JS behaviour:
- Maintains `history` array in memory
- `POST /api/chat` with `{message, history}` on send
- Renders `data.reply` as text bubble; renders `data.data` (if present) as a JSON pre-block labelled "Data"
- No chart rendering, no dashboard UI, no structured data visualisation
- No external JS libraries — Canvas API or inline SVG must be used for Feature 02 charts

---

## 3. Current State Summary

### What Works Today (Feature 01)

| Capability | Status | Notes |
|---|---|---|
| Natural-language chat, single FX pair | Working | `get_exchange_rate` tool |
| Multi-pair comparison | Working | `get_exchange_rates` tool |
| Currency list query | Working | `list_supported_currencies` tool |
| Live spot rates | Working | `/live` endpoint |
| Historical rate (single date) | Working | `/historical?date=YYYY-MM-DD` endpoint |
| Non-USD cross-rates | Working | USD triangulation in connector |
| Conversation history | Working | `history` passed through on each request |
| MockConnector for tests | Working | Error/unsupported injection via constructor |
| 90% coverage gate | Working | `pytest-cov` configured |

### Known Gaps & Limitations

| ID | Gap | Impact |
|---|---|---|
| GAP-01 | Free tier: ~100 req/month quota | All automated tests must use MockConnector |
| GAP-02 | Free tier: USD base only (non-USD pairs need 2 API calls) | Extra latency for cross-rates |
| GAP-03 | MockConnector ignores `date` param — static rates for all dates | Feature 02 historical trend tests will be inaccurate without fix |
| GAP-04 | No `.env.example` at project root — it exists only implicitly | New developers may miss it |
| GAP-05 | `ChatResponse.data` is untyped `Any` | Frontend can't rely on a stable schema |
| GAP-06 | CORS `allow_origins="*"` — PoC shortcut, not production-safe | Document before any deployment |
| GAP-07 | No retry logic in ExchangeRateHostConnector | Transient failures surface immediately as 503 |

---

## 4. Data Flows

### 4.1 Chat Request (Feature 01 — end to end)

```
1. User types message → JS sends:
   POST /api/chat
   {"message": "What was EUR/USD on 1 March 2026?", "history": [...]}

2. router.py → run_agent(message, history, connector)

3. agent.py builds messages list:
   [{"role":"system", content: SYSTEM_PROMPT},
    ...history...,
    {"role":"user", "content": "What was EUR/USD on 1 March 2026?"}]

4. openai.chat.completions.create(model="gpt-4o", tools=TOOL_DEFINITIONS, messages=...)
   → GPT-4o returns tool_call:
     get_exchange_rate(base="EUR", target="USD", date="2026-03-01")

5. dispatch_tool("get_exchange_rate", {base,target,date}, connector)
   → connector.get_exchange_rate("EUR", "USD", "2026-03-01")

6. ExchangeRateHostConnector._fetch_usd_rates(["EUR","USD"], "2026-03-01")
   → GET https://api.exchangerate.host/historical
     ?date=2026-03-01&source=USD&currencies=EUR&access_key=...
   → {"USDEUR": 0.9201, "USDUSD": 1.0}
   → triangulate: EUR/USD = USDUSD / USDEUR = 1.0 / 0.9201 = 1.0868
   → returns {"base":"EUR","target":"USD","rate":1.0868,"date":"2026-03-01","source":"exchangerate.host"}

7. Tool result appended to messages; second OpenAI call:
   → GPT-4o returns: "The EUR/USD rate on 1 March 2026 was 1.0868."

8. run_agent returns {reply: "...", data: {...rate dict...}, tool_used: "get_exchange_rate"}

9. router returns ChatResponse; JS renders reply bubble + data block
```

### 4.2 Connector `date` Parameter Behaviour

| Scenario | `date` value | API endpoint used |
|---|---|---|
| Latest rate | `None` (omitted) | `/live` |
| Historical rate | `"YYYY-MM-DD"` string | `/historical?date=YYYY-MM-DD` |

Both `get_exchange_rate` and `get_exchange_rates` accept the optional `date` parameter with identical semantics. The GPT-4o tool schema marks `date` as optional with description `"Optional date in YYYY-MM-DD format for historical rates."`

### 4.3 USD Triangulation Detail

For any non-USD base (e.g. EUR/GBP):

```python
# Single API call fetches both legs
quotes = await _fetch_usd_rates([base, target], date)
# quotes = {"USDEUR": 0.9201, "USDGBP": 0.7856}
rate = quotes[f"USD{target}"] / quotes[f"USD{base}"]
# EUR/GBP = 0.7856 / 0.9201 = 0.8538
```

Counts as **1 API call** (both currencies fetched together), not 2.

---

## 5. Feature 02 Context — FX Dashboard

### 5.1 What Needs to Be Added

Feature 02 adds a **historical rate trend dashboard** alongside the existing chat interface. The dashboard visualises rate data over time — it does NOT replace chat.

**New capabilities required:**
- New backend endpoint (e.g. `POST /api/dashboard`) that accepts a dashboard spec and returns structured time-series data
- Extended connector or new connector method to fetch rates across a date range (multiple sequential calls to `/historical`, one per day)
- New Pydantic models for dashboard request/response
- Frontend dashboard panel rendering (pure JS + Canvas API or SVG — no external libraries)
- Dashboard state management in the single `index.html` file

### 5.2 Dashboard Types (proposed)

| Type | Description | Data shape |
|---|---|---|
| `single_pair_trend` | Line chart of one currency pair over N days | `[{date, rate}]` |
| `multi_pair_comparison` | Multi-line chart comparing several pairs on same axis | `[{pair, series: [{date, rate}]}]` |
| `currency_heatmap` | Grid showing % change for N currencies vs base over a period | `[{base, target, pct_change}]` |

### 5.3 Multiple Panels Per Dashboard

A dashboard is a named container holding 1–N panels. Each panel has a type, a currency pair (or pairs), and a date range.

```json
{
  "dashboard_id": "morning-brief",
  "panels": [
    {"panel_id": "p1", "type": "single_pair_trend", "base": "EUR", "target": "USD", "days": 30},
    {"panel_id": "p2", "type": "multi_pair_comparison", "base": "USD", "targets": ["EUR","GBP","JPY"], "days": 7},
    {"panel_id": "p3", "type": "currency_heatmap", "base": "USD", "targets": ["EUR","GBP","JPY","AUD"], "days": 1}
  ]
}
```

### 5.4 API Quota Constraint

**Critical**: exchangerate.host free tier = ~100 req/month. Each day in a date range = 1 API call.

- A 30-day single-pair trend = 30 API calls
- A 7-day 3-pair dashboard = 7 calls (batch currencies per day)
- A dashboard with multiple panels sharing the same date+base can share calls

**Mitigations required:**
- Batch all currency targets for a given date into one `/historical` call
- Add response caching (in-memory dict keyed by `(date, base, targets_frozenset)`) to avoid duplicate calls within a session
- Enforce a hard limit on date range (e.g. max 30 days) in the API
- All Feature 02 tests must use MockConnector (never live API)

### 5.5 Frontend Constraints

- Must remain a **single `frontend/index.html`** file — no build step, no bundler
- No external JS libraries (no Chart.js, D3, etc.) — use Canvas 2D API or inline SVG
- CSS Grid or Flexbox for multi-panel layout
- Dashboard and chat must coexist in the same page (e.g. tabs or side-by-side layout)

---

## 6. Specialist Briefs

### Business Analyst
**Your job:** Define dashboard requirements, user stories, and acceptance criteria for Feature 02.

What you need to know:
- Feature 01 delivered chat-only FX queries. Feature 02 adds a visual dashboard layer — it must coexist with chat in the same page.
- Three proposed dashboard types: `single_pair_trend` (line chart), `multi_pair_comparison` (multi-line), `currency_heatmap` (grid of % changes). You must validate these with stakeholders and write formal acceptance criteria.
- A dashboard contains 1–N panels. Each panel specifies type, currencies, and date range.
- Hard constraint: max ~100 API calls/month total. A 30-day trend costs 30 calls. Date range must be capped (suggest max 30 days) and this must be an explicit acceptance criterion.
- The `ChatResponse` model has an untyped `data: Any` field. Feature 02 needs a typed `DashboardResponse` model — you must define the data contract.
- Historical rates are available via `/historical?date=YYYY-MM-DD` (confirmed working on free tier, EOD rates only — not intraday).
- All supported currencies: USD, EUR, GBP, JPY, AUD, CAD, CHF, CNY, HKD, SGD, NZD (11 currencies from MockConnector; live list via `list_supported_currencies` tool).

### Data Engineer
**Your job:** Design the historical data schema and connector contract for Feature 02.

What you need to know:
- The connector interface is in `backend/connectors/base.py`. The ABC has 3 methods: `get_exchange_rate`, `get_exchange_rates`, `list_supported_currencies`. All accept optional `date: str` (YYYY-MM-DD).
- There is **no** existing method for fetching a date range. You must design and add `get_exchange_rate_series(base, target, start_date, end_date) -> list[dict]` and `get_exchange_rates_series(base, targets, start_date, end_date) -> list[dict]` to the ABC.
- The ExchangeRateHostConnector must implement these by looping over dates and calling `/historical` once per date, batching all targets per date into a single call to minimise quota usage.
- Add in-memory caching keyed by `(date, frozenset(currencies))` to avoid duplicate API calls within a session.
- The canonical rate dict is `{base, target, rate, date, source}`. The series return type is a list of these dicts.
- MockConnector ignores `date` today — you must extend it to return deterministic per-date variation (e.g. `base_rate * (1 + 0.001 * day_offset)`) so historical trend tests produce meaningful data.
- Never exceed 30 days in a single series request — enforce in the connector, not just the API layer.

### SRE / Architect
**Your job:** Design the backend architecture for the dashboard endpoint and data pipeline.

What you need to know:
- Current entry points: `backend/main.py` (app factory), `backend/router.py` (single route). Add a new router or extend the existing one with `POST /api/dashboard`.
- The connector is stored on `app.state.connector` and injected at startup via `create_connector()` in `main.py`. The dashboard endpoint follows the same pattern.
- The dashboard endpoint receives a `DashboardRequest` (list of panel specs) and returns a `DashboardResponse` (list of panel results with time-series data).
- Key architectural concern: a dashboard with multiple panels and a 30-day range could make up to 30 API calls sequentially. Consider parallel execution (`asyncio.gather`) across panels where panels share no date overlap, but be aware that batching by date (all targets in one call) is more quota-efficient than parallelising.
- In-memory cache for `(date, frozenset(currencies))` → rate dict must live at the connector level, not the route level, so it is shared across requests in a session.
- No external caching infrastructure (Redis, etc.) for PoC — in-memory only.
- The existing `POST /api/chat` route and its agent loop are unchanged — dashboard is a separate code path.
- CORS and static file serving are already configured in `main.py`; no changes needed there.

### QA Expert
**Your job:** Write test cases and a code review checklist for Feature 02.

What you need to know:
- All tests live under `backend/tests/`. Structure: `unit/`, `agent/`, `e2e/`. Add `unit/test_connector_series.py` and `e2e/test_dashboard_api.py` as new files.
- **Never use live API in tests** — MockConnector only. The free tier quota is ~100 req/month; automated tests must not consume it.
- MockConnector needs per-date variation before trend tests are meaningful. Coordinate with Data Engineer.
- The `conftest.py` at `backend/tests/conftest.py` provides the `app_client` fixture (FastAPI TestClient with MockConnector injected). Extend it or add a `dashboard_client` fixture.
- Key test scenarios for Feature 02:
  - Happy path: 7-day single-pair trend returns 7 data points
  - Multi-panel dashboard: 2 panels, correct panel IDs in response
  - Date range enforcement: >30 days returns 422
  - Caching: two panels sharing the same date+base do not cause duplicate connector calls
  - Connector error mid-series: partial data or 503 depending on design decision
  - All existing Feature 01 tests (27 cases) must continue to pass unchanged
- Coverage gate remains 90% on `backend/`.

### Full Stack Engineer
**Your job:** Produce an implementation plan and implement Feature 02 across backend and frontend.

What you need to know:
- **Backend**: Add `DashboardRequest`/`DashboardResponse` Pydantic models to `backend/models.py`. Add `POST /api/dashboard` to `backend/router.py`. Connector series methods go in `backend/connectors/base.py` (ABC) and both concrete connectors.
- **Frontend**: The entire UI is `frontend/index.html` — one file, no build step, no external JS libraries. The current file is ~229 lines. Add dashboard UI without breaking the chat section.
  - Layout: tabs ("Chat" / "Dashboard") or split-pane — choose the simpler option
  - Charts: use Canvas 2D API (`<canvas>` + `ctx.lineTo`) for line charts; CSS Grid for heatmap
  - Dashboard builder: form inputs for panel type, currencies, date range; "Add Panel" button; "Run Dashboard" button
  - Fetch `POST /api/dashboard` with the panel spec; render each panel result
- **Key constraint**: No external JS libraries. No Chart.js, no D3, no Bootstrap.
- **Existing code to preserve unchanged**: `POST /api/chat` flow, `run_agent`, all connector methods (`get_exchange_rate`, `get_exchange_rates`, `list_supported_currencies`), all existing tests.
- **Config**: `USE_MOCK_CONNECTOR=false` in `.env` for manual testing; `USE_MOCK_CONNECTOR=true` in any CI/automated context.

### Tech Writer
**Your job:** Update the user guide and developer guide for Feature 02.

What you need to know:
- Existing guide is at `docs/user_guide.md`. It covers: prerequisites, setup steps, how to run, how to use the chat interface, how to extend the connector, API reference for `POST /api/chat`.
- Feature 02 adds: a dashboard UI section (how to create a dashboard, add panels, interpret charts), a new API reference section for `POST /api/dashboard` (request schema, response schema, error codes), and a developer guide section on adding new dashboard panel types.
- Supported currencies: USD, EUR, GBP, JPY, AUD, CAD, CHF, CNY, HKD, SGD, NZD.
- Quota constraint must be prominently documented: free tier = ~100 req/month; a 30-day dashboard uses ~30 calls; recommend `USE_MOCK_CONNECTOR=true` for development.
- Historical rates are EOD (end-of-day) only — document this limitation clearly so users do not expect intraday granularity.
- The `.env.example` variables relevant to Feature 02 are the same as Feature 01 (`OPENAI_API_KEY`, `EXCHANGERATE_API_KEY`, `USE_MOCK_CONNECTOR`, `OPENAI_MODEL`, `CORS_ORIGINS`) — no new env vars expected.

---

_End of team context document._





