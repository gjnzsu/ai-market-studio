# AI Market Studio — Architecture Design

> Author: SRE/AI Architect Agent
> Date: 2026-03-26
> Status: Draft — Feature 02 (FX Rate Trend Dashboard)

---

## 1. System Overview

AI Market Studio is a Proof-of-Concept FX market data chatbot. Users ask natural-language questions about foreign exchange rates; the system retrieves live or historical data and replies in plain language. Feature 02 extends this with a visual dashboard layer: users can request trend charts, multi-pair comparisons, and rate heatmaps rendered in-browser using the Canvas 2D API.

```
┌─────────────────────────────────────────────────────────────────┐
│                   Chat + Dashboard UI (Browser)                  │
│         frontend/index.html — HTML + Vanilla JS + Canvas 2D      │
└──────────────┬──────────────────────────┬───────────────────────┘
               │  POST /api/chat          │  POST /api/dashboard
               ▼                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Backend API (FastAPI)                        │
│   main.py · router.py · models.py · config.py · middleware       │
└───────────────────────────┬─────────────────────────────────────┘
                            │  await agent.run(...)  /  await build_dashboard(...)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI Agent Layer                                │
│         agent/agent.py  ·  agent/tools.py                        │
│         GPT-4o function-calling loop (OpenAI SDK)                │
└───────────────────────────┬─────────────────────────────────────┘
                            │  await connector.get_historical_rates(...)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Data Connector Layer                            │
│   connectors/base.py (ABC)                                       │
│   connectors/exchangerate_host.py  ·  connectors/mock_connector.py │
│   connectors/cache.py  (in-process rate cache)                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │  HTTPS GET  (batched, cached)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│               Market Data Source                                 │
│         https://api.exchangerate.host  (EOD rates, free tier)    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Feature 01 — Delivered (Baseline)

- Natural-language chat for FX spot rates (live and historical single-date lookups)
- GPT-4o selects from 3 tools: `get_exchange_rate`, `get_exchange_rates`, `list_supported_currencies`
- Non-USD cross-rates via USD triangulation (transparent to caller)
- MockConnector with error injection for all automated tests
- 90% coverage gate; tests never hit live API

---

## 3. Feature 02 — FX Rate Trend Dashboard

### 3.1 Goals

1. Allow users to render multi-day historical rate trend charts directly in the browser.
2. Support three dashboard types: **single-pair trend**, **multi-pair comparison**, **cross-rate heatmap**.
3. Support multiple panels per dashboard, each independently configurable.
4. Respect the 100 req/month free-tier quota via batching and an in-process cache.
5. Keep the single-file frontend constraint (no build step, no external JS libraries).

### 3.2 Supported Currencies

USD, EUR, GBP, JPY, AUD, CAD, CHF, CNY, HKD, SGD, NZD (11 currencies).

### 3.3 Data Granularity

End-of-day (EOD) only. Intraday data is not available on the free tier and is not in scope.

---

## 4. New API Endpoints

### 4.1  `POST /api/dashboard`

Builds dashboard data for one or more panels. The frontend sends a dashboard config; the backend resolves all required historical rate series and returns structured time-series data ready for Canvas rendering.

#### Request

```json
{
  "dashboard": {
    "id": "dash-001",
    "title": "My FX Dashboard",
    "type": "multi_panel",
    "panels": [
      {
        "id": "panel-1",
        "type": "trend",
        "base_currency": "USD",
        "quote_currency": "EUR",
        "start_date": "2026-02-24",
        "end_date": "2026-03-25"
      },
      {
        "id": "panel-2",
        "type": "comparison",
        "base_currency": "USD",
        "quote_currencies": ["EUR", "GBP", "JPY"],
        "start_date": "2026-02-24",
        "end_date": "2026-03-25"
      },
      {
        "id": "panel-3",
        "type": "heatmap",
        "currencies": ["USD", "EUR", "GBP", "JPY"],
        "date": "2026-03-25"
      }
    ]
  }
}
```

#### Response — success (HTTP 200)

```json
{
  "dashboard_id": "dash-001",
  "title": "My FX Dashboard",
  "panels": [
    {
      "id": "panel-1",
      "type": "trend",
      "series": [
        {
          "label": "USD/EUR",
          "data": [
            {"date": "2026-02-24", "rate": 0.9210},
            {"date": "2026-02-25", "rate": 0.9198}
          ]
        }
      ]
    },
    {
      "id": "panel-2",
      "type": "comparison",
      "series": [
        {"label": "USD/EUR", "data": [{"date": "2026-02-24", "rate": 0.9210}]},
        {"label": "USD/GBP", "data": [{"date": "2026-02-24", "rate": 0.7890}]},
        {"label": "USD/JPY", "data": [{"date": "2026-02-24", "rate": 149.55}]}
      ]
    },
    {
      "id": "panel-3",
      "type": "heatmap",
      "matrix": {
        "currencies": ["USD", "EUR", "GBP", "JPY"],
        "values": [
          [1.0,    0.9210, 0.7890, 149.55],
          [1.0857, 1.0,    0.8567, 162.38],
          [1.2674, 1.1672, 1.0,    189.54],
          [0.00668,0.00616,0.00527,1.0   ]
        ]
      }
    }
  ],
  "meta": {
    "quota_calls_used": 3,
    "cache_hits": 0,
    "generated_at": "2026-03-26T10:00:00Z"
  }
}
```

#### Error Responses

| HTTP Status | Code | Meaning |
|---|---|---|
| 400 | `invalid_panel_type` | `type` not in `[trend, comparison, heatmap]` |
| 400 | `invalid_currency` | Currency code not in supported set |
| 400 | `invalid_date_range` | `start_date` > `end_date`, or range > 365 days |
| 400 | `too_many_panels` | More than 6 panels in one request |
| 422 | `validation_error` | Pydantic schema validation failure |
| 503 | `connector_error` | Upstream exchangerate.host unavailable |
| 504 | `connector_timeout` | Upstream request exceeded 10 s |

### 4.2  `GET /api/rates/history`

Optional lightweight endpoint for direct historical range retrieval (used by the agent tool and can be called from the frontend directly for simple use cases).

#### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `base` | string | yes | Base currency (e.g. `USD`) |
| `quote` | string | yes | Quote currency (e.g. `EUR`) |
| `start_date` | string (ISO 8601) | yes | Inclusive start date |
| `end_date` | string (ISO 8601) | yes | Inclusive end date |

#### Response (HTTP 200)

```json
{
  "base": "USD",
  "quote": "EUR",
  "start_date": "2026-02-24",
  "end_date": "2026-03-25",
  "rates": [
    {"date": "2026-02-24", "rate": 0.9210},
    {"date": "2026-02-25", "rate": 0.9198}
  ]
}
```

---

## 5. Data Models

### 5.1 Pydantic Request/Response Models (`backend/models.py`)

```python
# Panel configs
class TrendPanelConfig(BaseModel):
    id: str
    type: Literal["trend"]
    base_currency: str
    quote_currency: str
    start_date: date
    end_date: date

class ComparisonPanelConfig(BaseModel):
    id: str
    type: Literal["comparison"]
    base_currency: str
    quote_currencies: list[str]          # 2–5 currencies
    start_date: date
    end_date: date

class HeatmapPanelConfig(BaseModel):
    id: str
    type: Literal["heatmap"]
    currencies: list[str]                # 2–6 currencies
    date: date

PanelConfig = Annotated[
    TrendPanelConfig | ComparisonPanelConfig | HeatmapPanelConfig,
    Field(discriminator="type")
]

class DashboardConfig(BaseModel):
    id: str
    title: str
    type: Literal["multi_panel"] = "multi_panel"
    panels: list[PanelConfig]            # 1–6 panels

class DashboardRequest(BaseModel):
    dashboard: DashboardConfig

# Response structures
class RatePoint(BaseModel):
    date: date
    rate: float

class Series(BaseModel):
    label: str
    data: list[RatePoint]

class TrendPanelData(BaseModel):
    id: str
    type: Literal["trend"]
    series: list[Series]                 # always 1 series

class ComparisonPanelData(BaseModel):
    id: str
    type: Literal["comparison"]
    series: list[Series]                 # N series, one per quote currency

class HeatmapMatrix(BaseModel):
    currencies: list[str]
    values: list[list[float]]

class HeatmapPanelData(BaseModel):
    id: str
    type: Literal["heatmap"]
    matrix: HeatmapMatrix

PanelData = TrendPanelData | ComparisonPanelData | HeatmapPanelData

class DashboardMeta(BaseModel):
    quota_calls_used: int
    cache_hits: int
    generated_at: datetime

class DashboardResponse(BaseModel):
    dashboard_id: str
    title: str
    panels: list[PanelData]
    meta: DashboardMeta
```

### 5.2 Connector ABC Extension (`backend/connectors/base.py`)

New abstract method added to `MarketDataConnector`:

```python
@abstractmethod
async def get_historical_rates(
    self,
    base: str,
    quote: str,
    start_date: date,
    end_date: date,
) -> list[dict]:  # [{"date": "YYYY-MM-DD", "rate": float}, ...]
    ...
```

### 5.3 In-Process Cache Schema (`backend/connectors/cache.py`)

```python
# Key: (base, quote, date_str)  →  Value: float (EOD rate)
# TTL: 24 hours (EOD rates are stable once published)
# Max size: 3 650 entries (~10 years × 365 days × 1 pair)
# Implementation: dict + timestamp; no external dependency
cache: dict[tuple[str, str, str], tuple[float, float]] = {}
#                                                             rate  stored_at_epoch
```

---

## 6. Agent Tool Additions

Two new GPT-4o tool definitions are added in `backend/agent/tools.py`.

### 6.1 `get_historical_rate_series`

```json
{
  "type": "function",
  "function": {
    "name": "get_historical_rate_series",
    "description": "Retrieve end-of-day exchange rates for a currency pair over a date range. Returns a time-ordered list of {date, rate} objects. Maximum range is 365 days.",
    "parameters": {
      "type": "object",
      "properties": {
        "base_currency": {
          "type": "string",
          "description": "The base (from) currency ISO 4217 code, e.g. USD"
        },
        "quote_currency": {
          "type": "string",
          "description": "The quote (to) currency ISO 4217 code, e.g. EUR"
        },
        "start_date": {
          "type": "string",
          "description": "Start date in YYYY-MM-DD format (inclusive)"
        },
        "end_date": {
          "type": "string",
          "description": "End date in YYYY-MM-DD format (inclusive)"
        }
      },
      "required": ["base_currency", "quote_currency", "start_date", "end_date"]
    }
  }
}
```

### 6.2 `build_dashboard`

```json
{
  "type": "function",
  "function": {
    "name": "build_dashboard",
    "description": "Build a multi-panel FX rate dashboard. Returns structured panel data that the frontend will render as charts. Supported panel types: trend (single pair over time), comparison (multiple pairs over time), heatmap (cross-rate matrix for a single date).",
    "parameters": {
      "type": "object",
      "properties": {
        "title": {
          "type": "string",
          "description": "Dashboard title"
        },
        "panels": {
          "type": "array",
          "description": "List of panel configurations (1–6 panels)",
          "items": {
            "type": "object"
          },
          "minItems": 1,
          "maxItems": 6
        }
      },
      "required": ["title", "panels"]
    }
  }
}
```

---

## 7. Frontend Component Architecture

### 7.1 Single-File Constraint

All dashboard UI lives in `frontend/index.html`. No external JS libraries, no build step. Charts are rendered using the browser's native **Canvas 2D API**.

### 7.2 UI Sections

```
frontend/index.html
├── <style>         — CSS for chat panel, dashboard panel, canvas sizing
├── <div#chat>      — existing chat interface (Feature 01, unchanged)
├── <div#dashboard> — new dashboard builder section
│   ├── Dashboard form (title, add-panel controls)
│   ├── Panel list (dynamic: add/remove panels)
│   └── <div#panels-container> — rendered panel canvases
└── <script>
    ├── chatModule      — existing chat logic (unchanged)
    ├── dashboardModule — new dashboard logic
    │   ├── buildDashboardConfig()  — collects form state → DashboardRequest JSON
    │   ├── submitDashboard()       — POST /api/dashboard, handles response
    │   ├── renderPanel(panelData)  — dispatcher: trend/comparison/heatmap
    │   ├── renderTrend(ctx, data)  — Canvas line chart
    │   ├── renderComparison(ctx, data) — Canvas multi-line chart
    │   └── renderHeatmap(ctx, data)    — Canvas color matrix
    └── init()          — wire up event listeners
```

### 7.3 Dashboard Types and Panel Rendering

#### Trend Panel (single-pair line chart)
- X-axis: dates, Y-axis: exchange rate
- Canvas `lineTo` / `stroke` for the rate series
- Axis labels drawn with `fillText`

#### Comparison Panel (multi-pair line chart)
- Same axes as trend; each pair rendered in a distinct colour
- Legend drawn top-right using `fillRect` + `fillText`
- Colours from a fixed palette (6 colours; max 5 pairs per panel)

#### Heatmap Panel (N×N colour matrix)
- Each cell: `fillRect` with colour interpolated from green (low rate) → red (high rate) per column
- Cell labels: `fillText` with the rate value centred in the cell
- Row/column headers: currency codes

### 7.4 Panel Configuration UI

Each panel added by the user exposes:
- Panel type selector (trend / comparison / heatmap)
- Currency selectors (base + quote, or multi-select for comparison/heatmap)
- Date range pickers (start_date, end_date) — hidden for heatmap (single date)
- Remove button

All controls are plain `<select>`, `<input type="date">`, `<button>` — no library.

---

## 8. Quota Management and Caching Strategy

### 8.1 The Constraint

exchangerate.host free tier: ~100 API requests/month. **CONFIRMED:** `/timeseries` endpoint is **NOT available on the free tier** — it requires the Basic plan ($14.99/month). The free tier provides only `/historical` (single date per call) and `/live`. Therefore every historical date requires one separate API call. There is no batching available on the free tier.

### 8.2 Batching Strategy

When `POST /api/dashboard` is received:

1. **Decompose panels** into a set of unique `(base, quote, date)` tuples across all requested dates.
2. **Check cache** — for each `(base, quote, date)`, look up in `cache.py`. Cached dates cost 0 calls.
3. **Fetch uncached dates** — one `/historical` call per uncached `(base, quote, date)` tuple.
4. **Populate cache** with all returned rates (TTL 24 h).
5. **Assemble response** from cache.

> **CONFIRMED: No batching available on free tier.** `/timeseries` requires the Basic plan ($14.99/month). Free tier uses `/historical` only — 1 call per date per pair. The in-memory cache is the **sole quota mitigation**: warm cache loads cost 0 calls. `USE_MOCK_CONNECTOR=true` is mandatory for all development and CI.

> **Upgrade path:** Basic plan ($14.99/month) provides `/timeseries` (1 call per pair for any date range, 10k req/month). At that tier, a 30-day 3-pair dashboard = 3 calls and `MAX_HISTORICAL_DAYS` can safely be raised to 365.

#### Guardrails (quota protection — free tier defaults)

| Guardrail | Free tier default | Basic plan default | Env var override |
|---|---|---|---|
| Max date range per panel | **7 days** | 365 days | `MAX_HISTORICAL_DAYS` |
| Max pairs per dashboard | 5 | 5 | `MAX_DASHBOARD_PAIRS` |
| Max panels per dashboard | 6 | 6 | — (hard limit) |

#### Quota Consumption (free tier — `/historical` per-date calls)

| Dashboard | Days | Pairs | Cache cold | API calls |
|---|---|---|---|---|
| 7-day single trend | 7 | 1 | yes | 7 |
| 7-day 3-pair comparison | 7 | 3 | yes | 21 |
| 7-day 3-pair + heatmap (5 currencies = 10 pairs, 1 date) | 2 panels | 3 + 10 | cold | 31 |
| Any dashboard, repeated load | any | any | warm | 0 |
| 30-day 3-pair (if MAX_HISTORICAL_DAYS overridden to 30) | 30 | 3 | cold | 90 |

### 8.3 Cache Implementation

- **Location**: `backend/connectors/cache.py` — module-level dict (in-process, no Redis dependency for PoC)
- **Key**: `(base: str, quote: str, date: str)` → `(rate: float, stored_epoch: float)`
- **TTL**: 24 hours (EOD rates do not change once published)
- **Eviction**: lazy — checked on read; no background sweep needed at PoC scale
- **Thread safety**: FastAPI runs in a single async event loop; `asyncio.Lock` guards cache writes

### 8.4 Development Recommendation

Set `USE_MOCK_CONNECTOR=true` in `.env` during development and in all CI/CD pipelines. MockConnector returns deterministic synthetic rates, uses 0 quota, and supports error injection. This is **mandatory** for CI — live connector calls in automated tests will exhaust the monthly quota within days.

### 8.5 Production Scaling Notes

The in-process dict cache is sufficient for PoC single-process deployments. For production scale, replace with:

- **Redis** shared cache — survives restarts, shared across multiple worker processes
- **Quota counter** — atomic Redis counter per calendar month; reject requests when counter approaches 100
- **Circuit breaker** — open circuit after 3 consecutive 5xx from exchangerate.host; return cached data or 503 fast-fail
- **Retry with exponential backoff** — not implemented in PoC connector; add for production to handle transient upstream errors

---

## 9. SLIs and SLOs

### 9.1 `POST /api/dashboard`

| SLI | SLO | Measurement |
|---|---|---|
| Availability | ≥ 99% of requests return HTTP 2xx or expected 4xx | FastAPI middleware counter |
| Latency (cache warm) | p95 < 500 ms | Middleware timer |
| Latency (cache cold, 1 pair, 30 days) | p95 < 3 s | Middleware timer |
| Latency (cache cold, 6 panels, max pairs) | p95 < 10 s | Middleware timer |
| Error rate (5xx) | < 1% of requests | Middleware counter |

### 9.2 `GET /api/rates/history`

| SLI | SLO | Measurement |
|---|---|---|
| Availability | ≥ 99% | Middleware counter |
| Latency (cache warm) | p95 < 200 ms | Middleware timer |
| Latency (cache cold) | p95 < 3 s | Middleware timer |

### 9.3 `POST /api/chat` (unchanged)

| SLI | SLO |
|---|---|
| Availability | ≥ 99% |
| Latency | p95 < 5 s (GPT-4o round-trip dominates) |

### 9.4 Observability

- Structured JSON logs on every request: method, path, status, latency_ms, cache_hits, quota_calls
- `meta` block in `DashboardResponse` exposes `quota_calls_used` and `cache_hits` to the client for transparency
- No external monitoring stack in PoC — logs to stdout, captured by Uvicorn

---

## 10. File Ownership

### 10.1 Modified Files

| File | Owner | Change Summary |
|---|---|---|
| `backend/router.py` | Backend specialist | Add `POST /api/dashboard` and `GET /api/rates/history` routes |
| `backend/models.py` | Backend specialist | Add all dashboard Pydantic models (Section 5.1) |
| `backend/agent/tools.py` | AI Agent specialist | Add `get_historical_rate_series` and `build_dashboard` tool definitions and dispatch |
| `backend/agent/agent.py` | AI Agent specialist | Register new tools; handle `build_dashboard` tool call → delegate to dashboard service |
| `backend/connectors/base.py` | Data Engineer | Add `get_historical_rates` abstract method |
| `backend/connectors/exchangerate_host.py` | Data Engineer | Implement `get_historical_rates` via `/timeseries` endpoint |
| `backend/connectors/mock_connector.py` | Data Engineer | Implement `get_historical_rates` with synthetic data + error injection |
| `frontend/index.html` | Frontend specialist | Add dashboard UI section and `dashboardModule` JS |

### 10.2 New Files

| File | Owner | Purpose |
|---|---|---|
| `backend/connectors/cache.py` | Data Engineer | In-process rate cache (dict + TTL) |
| `backend/dashboard.py` | Backend specialist | `build_dashboard_response()` service function — panel decomposition, cache lookup, batched fetch, response assembly |
| `tests/unit/test_cache.py` | QA specialist | Cache TTL, hit/miss, eviction, concurrent write tests |
| `tests/unit/test_dashboard_service.py` | QA specialist | `build_dashboard_response()` unit tests with MockConnector |
| `tests/e2e/test_dashboard_api.py` | QA specialist | E2E tests for `POST /api/dashboard` via TestClient |

### 10.3 Unchanged Files

`backend/main.py`, `backend/config.py`, `tests/unit/test_connector.py`, `tests/unit/test_tools.py`, `tests/agent/test_agent.py`, `tests/e2e/test_chat_api.py`, `requirements.txt`, `.env.example`

---

## 11. Cross-Cutting Concerns

### 11.1 For QA Expert
- MockConnector **must** implement `get_historical_rates` with error injection support (simulate 503, timeout, partial data) before any dashboard tests can be written.
- New coverage gate applies: 90% line coverage must be maintained across all new files.
- Heatmap panels require N×(N-1)/2 unique pair lookups for an N-currency matrix (symmetric — each pair fetched once, diagonal self-pairs = 1.0 require no API call). Test boundary: 6 currencies = **15 pairs**.

### 11.2 For Data Engineer
- **CONFIRMED (2026-03-26):** `/timeseries` is NOT available on the free tier. Implementation uses `/historical` only — 1 call per date per pair. No batching is possible on the free tier.
- **Series-level triangulation pattern (REQUIRED):** For non-USD cross-rate historical panels (e.g. EUR/GBP), fetch `USD/base` series + `USD/quote` series (2 calls total regardless of date range if `/timeseries` were available; on free tier: 2 calls per date). Compute `base/quote = (USD/quote) / (USD/base)` locally per date, store derived cross-rate in cache under `(base, quote, date)`.
- On free tier with `/historical` fallback, a 7-day EUR/GBP panel costs 14 calls (2 per day). `MAX_HISTORICAL_DAYS=7` is the safe free-tier default.
- Cache key uses `(base, quote, date)` — always store the derived cross-rate, never the intermediate USD legs.
- Heatmap for N currencies = N×(N-1)/2 unique pairs (symmetric). A 5-currency heatmap = 10 pairs = 10 calls cold, 0 warm.

### 11.3 For Business Analyst
- Maximum 6 panels per dashboard is a quota-protection constraint, not a product decision — if the product requires more panels, quota management must be revisited.
- EOD-only granularity is a hard free-tier constraint. Intraday would require a paid plan.

---

## 12. Sequence Diagram — `POST /api/dashboard` (cache cold)

```
Browser          FastAPI           dashboard.py        cache.py        ExchangeRateHostConnector
  │                │                    │                  │                    │
  │─POST /api/─────▶│                    │                  │                    │
  │  dashboard      │                    │                  │                    │
  │                 │─build_dashboard────▶│                  │                    │
  │                 │    _response()      │                  │                    │
  │                 │                    │─lookup(pairs)────▶│                    │
  │                 │                    │◀─cache miss───────│                    │
  │                 │                    │─get_historical────────────────────────▶│
  │                 │                    │  _rates() × N     │                    │
  │                 │                    │◀─[{date,rate}]────────────────────────│
  │                 │                    │─store(pairs)─────▶│                    │
  │                 │                    │─assemble panels   │                    │
  │                 │◀─DashboardResponse─│                   │                    │
  │◀─HTTP 200───────│                    │                   │                    │
```

---

*End of Architecture Design Document.*