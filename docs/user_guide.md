# AI Market Studio — User Guide & Developer Guide

> **Version:** 2.0
> **Date:** 2026-03-26
> **Status:** Final — covers Feature 01 (Chat Interface) and Feature 02 (FX Rate Trend Dashboard)

---

## Table of Contents

**End-User Sections**
1. [What is AI Market Studio?](#1-what-is-ai-market-studio)
2. [Getting Started](#2-getting-started)
3. [Using the Chat Interface (Feature 01)](#3-using-the-chat-interface-feature-01)
4. [Using the FX Dashboard (Feature 02)](#4-using-the-fx-dashboard-feature-02)
5. [Supported Currencies](#5-supported-currencies)
6. [Troubleshooting](#6-troubleshooting)

**Developer Sections**
7. [Project Structure](#7-project-structure)
8. [Adding a New Connector](#8-adding-a-new-connector)
9. [Adding a New Agent Tool](#9-adding-a-new-agent-tool)
10. [Adding a New Dashboard Type](#10-adding-a-new-dashboard-type)
11. [Running Tests](#11-running-tests)
12. [API Reference](#12-api-reference)

---

# End-User Sections

---

## 1. What is AI Market Studio?

AI Market Studio is an AI-powered foreign exchange (FX) market data platform. It provides two interfaces:

- **Chat Interface (Feature 01):** Ask natural-language questions — "What is EUR/USD right now?" or "What was GBP/JPY on 1 March 2026?" — and receive plain-English answers backed by live and historical data.
- **FX Rate Trend Dashboard (Feature 02):** Build visual dashboards composed of multiple panels showing historical rate trends, multi-pair comparisons, and currency heatmaps, rendered in-browser.

The system uses GPT-4o (OpenAI) to interpret user intent, and fetches rate data from exchangerate.host. It is a clean, handoff-ready proof-of-concept targeting FX traders, finance analysts, and treasury teams.

> **Important — API quota:** The exchangerate.host free tier allows approximately **100 requests per month**. A single 30-day, 3-pair dashboard consumes ~90 calls. Use `USE_MOCK_CONNECTOR=true` for development and testing to avoid exhausting your quota.

---

## 2. Getting Started

### Prerequisites

| Requirement | Version / Notes |
|-------------|----------------|
| Python | 3.11 or higher |
| pip | Latest |
| OpenAI API key | GPT-4o access required |
| exchangerate.host API key | Free tier requires registration at exchangerate.host |
| Modern browser | Chrome, Firefox, Edge, or Safari |

### Installation

**Step 1 — Clone the repository**

```bash
git clone <repository-url>
cd ai-market-studio
```

**Step 2 — Create and activate a virtual environment**

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

**Step 3 — Install dependencies**

```bash
pip install -r requirements.txt
```

**Step 4 — Configure environment variables**

Copy the example file and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
# Required
OPENAI_API_KEY=sk-...
EXCHANGERATE_API_KEY=your_exchangerate_host_key

# Optional — GPT-4o is the default
OPENAI_MODEL=gpt-4o

# Set to true during development to avoid consuming live API quota
USE_MOCK_CONNECTOR=false

# Allowed origins for CORS (comma-separated)
CORS_ORIGINS=http://localhost:8000
```

> **Note:** No new environment variables are required for Feature 02. All Feature 02 functionality uses the same keys listed above.

**Step 5 — Start the server**

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The application is now available at **http://localhost:8000**.
Interactive API docs (Swagger UI) are at **http://localhost:8000/docs**.

---

## 3. Using the Chat Interface (Feature 01)

The chat interface lets you query live and historical FX rates in plain English.

### Accessing the Chat

Open **http://localhost:8000** in your browser. The chat panel appears on the page by default.

### Asking Questions

Type a question in the input box and press **Enter** or click **Send**.

**Example prompts:**

| What you want | What to type |
|---------------|-------------|
| Current spot rate | `What is the EUR/USD rate?` |
| Historical rate | `What was USD/JPY on 2025-12-01?` |
| Cross-rate | `What is GBP/CHF today?` |
| Multiple rates | `Show me EUR/USD, GBP/USD and AUD/USD rates` |
| Supported currencies | `Which currencies do you support?` |

### How It Works

1. Your message is sent to the backend via `POST /api/chat`.
2. GPT-4o interprets intent and selects one of three tools: `get_exchange_rate`, `get_exchange_rates`, or `list_supported_currencies`.
3. The selected tool calls the active data connector (live or mock).
4. The result is formatted and returned as a conversational reply.

For cross-rates not directly quoted (e.g., GBP/CHF), the system performs USD triangulation automatically — you simply ask for the pair you need.

### Chat Limitations

- Optimised for question-and-answer queries, not bulk data export.
- Historical data is **end-of-day (EOD) only** — intraday rates are not available on the free exchangerate.host tier.
- For visual trend analysis across time or multiple pairs, use the FX Dashboard (Feature 02).

---

## 4. Using the FX Dashboard (Feature 02)

The FX Rate Trend Dashboard provides panel-based visual analysis of historical exchange rates.

### Accessing the Dashboard

Click the **Dashboard** tab at the top of the page, or navigate to **http://localhost:8000/dashboard**.

### Selecting a Dashboard Type

When you create a dashboard you choose one of three types:

| Dashboard Type | Best For |
|---------------|----------|
| **Single-Pair Trend** | Tracking one currency pair over time as a line chart |
| **Multi-Pair Comparison** | Overlaying multiple pairs on one chart to compare relative movement |
| **Heatmap** | Spotting rate-change patterns across a grid of base × quote currencies |

**To create a dashboard:**

1. Click **+ New Dashboard** in the sidebar.
2. Enter a name.
3. Select a **Dashboard Type** from the dropdown.
4. Click **Create**.

### Adding and Configuring Panels

Each dashboard holds multiple independent panels. A panel is one chart or data widget.

**To add a panel:**

1. Open a dashboard and click **+ Add Panel**.
2. In the panel configuration drawer set:
   - **Panel type** — Line Chart, Bar Chart, Stats Summary, or Heatmap Table.
   - **Currency pair(s)** — one or more pairs (e.g., EUR/USD).
   - **Date range** — start and end date, or a preset (7 days, 30 days, 90 days).
   - **Granularity** — daily, weekly, or monthly data points.
3. Click **Save Panel**.

Panels are arranged in a CSS Grid layout. Drag panel headers to reorder; drag panel edges to resize.

**To edit a panel:** click the pencil icon on the panel header.
**To remove a panel:** click the trash icon and confirm.

> **Quota warning:** Each panel data fetch consumes exchangerate.host API calls: one call per currency pair per date in the range. A 30-day, 3-pair dashboard = ~90 calls. The free tier allows ~100 calls/month. Set `USE_MOCK_CONNECTOR=true` during development.

### Querying Historical Rates

Historical data is fetched when you save a panel with a past date range:

1. The frontend calls `POST /api/dashboard` with the panel configuration.
2. The backend retrieves EOD rates from the connector (or cache).
3. The panel chart renders with the returned data points.

Click **Refresh** on a panel to force a fresh fetch. The date range is capped at **31 calendar days per request** by default (set `MAX_HISTORICAL_DAYS` in `.env` to change).

> **Historical data is EOD only.** The exchangerate.host free tier provides end-of-day closing rates. Intraday (hourly/minute) rates are not available.

### Understanding the Charts

| Element | Meaning |
|---------|--------|
| X-axis | Date |
| Y-axis | Rate (units of quote currency per 1 base currency unit) |
| Tooltip | Exact rate and date on hover |
| Colour legend | Identifies each pair (Multi-Pair Comparison) |
| Cell colour | Magnitude of rate change — green = appreciation, red = depreciation (Heatmap) |
| Stats panel | Shows min, max, mean, and standard deviation for the selected period |

---

## 5. Supported Currencies

The following currencies are supported for both chat queries and dashboard panels.

| Code | Currency |
|------|----------|
| USD | US Dollar |
| EUR | Euro |
| GBP | British Pound Sterling |
| JPY | Japanese Yen |
| AUD | Australian Dollar |
| CAD | Canadian Dollar |
| CHF | Swiss Franc |
| CNY | Chinese Yuan Renminbi |
| HKD | Hong Kong Dollar |
| SGD | Singapore Dollar |
| NZD | New Zealand Dollar |

> For the live list, call `GET /api/v1/currencies`.

**Cross-rates:** Pairs not directly quoted against USD (e.g., GBP/CHF) are computed by USD triangulation:

```
GBP/CHF = (USD/CHF) / (USD/GBP)
```

This is transparent — simply ask for the pair you need.

---

## 6. Troubleshooting

### Server won't start

- Confirm Python 3.11+: `python --version`
- Confirm dependencies installed: `pip install -r requirements.txt`
- Confirm `.env` exists and contains `OPENAI_API_KEY` and `EXCHANGERATE_API_KEY`.

### "API key invalid" error

- Check for leading/trailing spaces in `.env` values.
- Confirm your OpenAI key has GPT-4o access.
- Confirm your exchangerate.host key is active (log in to their dashboard).

### Chat returns "I could not retrieve the rate"

- Check server logs for HTTP 4xx/5xx from the connector.
- If `USE_MOCK_CONNECTOR=false` you may have exhausted the free-tier quota (~100 req/month).
- Set `USE_MOCK_CONNECTOR=true` to verify the rest of the stack with synthetic data.

### Dashboard panel shows "No data"

- Confirm the date range is not in the future.
- Confirm the currency pair is in the supported list (Section 5).
- Check browser console for network errors (F12 → Console).
- Click **Refresh** on the panel.
- Confirm you have not exceeded the 31-day-per-request cap (`MAX_HISTORICAL_DAYS`).

### Historical data unavailable

- The exchangerate.host free tier historical endpoint availability is unconfirmed. Verify your plan at exchangerate.host, or use `USE_MOCK_CONNECTOR=true` for development.
- Historical data is EOD only — intraday rates will never be returned regardless of plan.

### Cross-rate is wrong or null

- Cross-rates require two sequential USD-based API calls. If either fails, the result is `null`.
- Check server logs for `triangulation error`.
- Verify both leg currencies are in the supported list.

### Quota exhausted mid-session

- The session-level quota enforcer (`QUOTA_LIMIT_PER_SESSION`) will return HTTP 429 once reached.
- Check remaining quota: `GET /api/v1/quota`.
- Set `USE_MOCK_CONNECTOR=true` and restart the server to continue working without consuming quota.

---

# Developer Sections

---

## 7. Project Structure

```
ai-market-studio/
├── backend/
│   ├── main.py                   # FastAPI app factory, startup, middleware
│   ├── router.py                 # All HTTP route definitions
│   ├── models.py                 # Pydantic request/response models
│   ├── config.py                 # Settings (env vars, feature flags)
│   ├── agent/
│   │   ├── agent.py              # GPT-4o function-calling loop
│   │   └── tools.py              # Tool definitions and dispatch
│   ├── connectors/
│   │   ├── base.py               # Abstract MarketDataConnector base class
│   │   ├── exchangerate_host.py  # Live data connector
│   │   ├── mock_connector.py     # Synthetic data connector (tests/dev)
│   │   └── cache.py              # In-process rate cache
│   └── dashboard/
│       └── dashboard.py          # build_dashboard_response() logic
├── frontend/
│   └── index.html                # Single-page UI (chat + dashboard tabs)
├── tests/
│   ├── unit/                     # Connector and model unit tests
│   ├── agent/                    # Agent layer tests (mocked OpenAI)
│   └── e2e/                      # End-to-end tests (TestClient + MockConnector)
├── docs/                         # All design and reference documents
├── .env.example
├── requirements.txt
└── README.md
```

### Architecture (5 Layers)

```
Chat UI + Dashboard UI  (frontend/index.html)
           │  POST /api/chat  │  POST /api/dashboard
           ▼                  ▼
     Backend API  (FastAPI — router.py)
           │
           ▼
  AI Agent Layer  (agent/agent.py + tools.py)
           │
           ▼
Data Connector Layer  (connectors/base.py ABC)
           │
           ▼
 Market Data Source  (exchangerate.host / MockConnector)
```

---

## 8. Adding a New Connector

All connectors implement the abstract base class in `backend/connectors/base.py`.

**Step 1 — Create the connector file**

```python
# backend/connectors/myconnector.py
from backend.connectors.base import MarketDataConnector
from decimal import Decimal
from datetime import date
from typing import list

class MyConnector(MarketDataConnector):

    async def get_exchange_rate(self, base: str, quote: str) -> Decimal:
        """Return current spot rate for base/quote."""
        ...

    async def get_exchange_rates(
        self, base: str, quotes: list[str]
    ) -> dict[str, Decimal]:
        """Return current spot rates for multiple quote currencies."""
        ...

    async def get_historical_rate(
        self, base: str, quote: str, on_date: date
    ) -> Decimal:
        """Return EOD rate for base/quote on a specific date."""
        ...

    async def get_historical_rates(
        self, base: str, quote: str, start: date, end: date
    ) -> list[dict]:
        """Return EOD rates for base/quote over a date range.
        Each dict: {"date": "YYYY-MM-DD", "rate": Decimal}
        """
        ...

    async def list_supported_currencies(self) -> list[str]:
        """Return list of supported ISO 4217 currency codes."""
        ...
```

**Step 2 — Register the connector in `config.py`**

Add a branch to the connector factory function that reads `USE_MOCK_CONNECTOR` and any new env vars your connector needs.

**Step 3 — Add unit tests**

Create `tests/unit/test_myconnector.py` using `respx` to mock HTTP calls. The MockConnector pattern in `mock_connector.py` is the reference implementation.

**Step 4 — Set `USE_MOCK_CONNECTOR=true` in CI**

Never allow CI to call a live API. Inject the MockConnector in all automated test runs.

---

## 9. Adding a New Agent Tool

Agent tools are defined in `backend/agent/tools.py` and dispatched in the same file.

**Step 1 — Define the tool schema**

Add a new entry to the `TOOLS` list following the OpenAI function-calling schema:

```python
{
    "type": "function",
    "function": {
        "name": "my_new_tool",
        "description": "What this tool does, in one sentence.",
        "parameters": {
            "type": "object",
            "properties": {
                "param_one": {
                    "type": "string",
                    "description": "Description of param_one."
                }
            },
            "required": ["param_one"]
        }
    }
}
```

**Step 2 — Implement the dispatch handler**

In the `dispatch_tool` function, add a branch for `"my_new_tool"`:

```python
elif name == "my_new_tool":
    result = await connector.some_method(args["param_one"])
    return {"result": str(result)}
```

**Step 3 — Add agent-layer tests**

In `tests/agent/`, add a fixture with a recorded OpenAI response that invokes `my_new_tool`, and assert that `dispatch_tool` returns the expected result using MockConnector.

---

## 10. Adding a New Dashboard Type

Dashboard types are defined in `backend/dashboard/dashboard.py` and rendered in `frontend/index.html`.

**Step 1 — Register the type in `models.py`**

Add the new type string to the `DashboardType` enum:

```python
class DashboardType(str, Enum):
    single_pair_trend = "single_pair_trend"
    multi_pair_comparison = "multi_pair_comparison"
    heatmap = "heatmap"
    my_new_type = "my_new_type"  # add here
```

**Step 2 — Implement the assembler in `dashboard.py`**

Add a handler branch inside `build_dashboard_response()`:

```python
elif request.dashboard_type == DashboardType.my_new_type:
    panels = await _build_my_new_type_panels(request, connector)
```

Implement `_build_my_new_type_panels()` to fetch data and return a list of `PanelData` objects.

**Step 3 — Implement the renderer in `index.html`**

The frontend receives panel data as JSON. Add a renderer function:

```javascript
function renderMyNewType(panel, canvasEl) {
    const ctx = canvasEl.getContext('2d');
    // draw using Canvas 2D API
}
```

Register it in the panel dispatch map so the correct renderer is called based on `panel.type`.

**Step 4 — Add tests**

Add a unit test in `tests/unit/` that calls `build_dashboard_response()` with `dashboard_type="my_new_type"` using MockConnector and asserts the correct panel structure is returned.

---

## 11. Running Tests

### Test Layout

| Directory | What it tests | Connector used |
|-----------|--------------|----------------|
| `tests/unit/` | Connectors, models, cache, dashboard assembler | MockConnector + respx |
| `tests/agent/` | GPT-4o tool dispatch, agent loop | Mocked OpenAI client (recorded fixtures) |
| `tests/e2e/` | Full HTTP request → response via FastAPI TestClient | MockConnector injected |

### Running All Tests

```bash
pytest --cov=backend --cov-report=term-missing
```

The 90% coverage gate is enforced. The run will fail if coverage drops below that threshold.

### Running a Specific Layer

```bash
# Unit tests only
pytest tests/unit/

# Agent tests only
pytest tests/agent/

# E2E tests only
pytest tests/e2e/
```

### Environment for Tests

Always run tests with MockConnector to avoid consuming live API quota:

```bash
USE_MOCK_CONNECTOR=true pytest
```

Or set `USE_MOCK_CONNECTOR=true` in your `.env` before running pytest.

> **CI requirement:** All CI pipelines must set `USE_MOCK_CONNECTOR=true`. Never allow CI to call a live external API.

---

## 12. API Reference

All endpoints are prefixed with `/api/v1`. The Swagger UI at `/docs` provides an interactive reference.

---

### `POST /api/chat`

Send a natural-language message and receive an AI-generated reply.

**Request body**

```json
{
  "message": "What is EUR/USD right now?",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | The user's current message |
| `history` | array | No | Prior conversation turns for context |

**Response — HTTP 200**

```json
{
  "reply": "The current EUR/USD rate is 1.0842."
}
```

**Error codes**

| Code | Meaning |
|------|---------|
| 400 | Malformed request body |
| 422 | Validation error (Pydantic) |
| 500 | Agent or connector error |
| 502 | Upstream API (OpenAI or exchangerate.host) unreachable |

---

### `POST /api/dashboard`

Build a dashboard response: fetch historical rate data and assemble panel payloads for frontend rendering.

**Request body**

```json
{
  "dashboard_type": "single_pair_trend",
  "panels": [
    {
      "panel_type": "line_chart",
      "pairs": ["EUR/USD"],
      "start_date": "2026-02-01",
      "end_date": "2026-03-01",
      "granularity": "daily"
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `dashboard_type` | string enum | Yes | `single_pair_trend`, `multi_pair_comparison`, or `heatmap` |
| `panels` | array | Yes | One or more panel configurations |
| `panels[].panel_type` | string enum | Yes | `line_chart`, `bar_chart`, `stats_summary`, or `heatmap_table` |
| `panels[].pairs` | array of strings | Yes | Currency pairs in `BASE/QUOTE` format |
| `panels[].start_date` | string (YYYY-MM-DD) | Yes | Start of date range |
| `panels[].end_date` | string (YYYY-MM-DD) | Yes | End of date range (max 31 days ahead of start by default) |
| `panels[].granularity` | string enum | No | `daily` (default), `weekly`, or `monthly` |

**Response — HTTP 200**

```json
{
  "dashboard_type": "single_pair_trend",
  "panels": [
    {
      "panel_type": "line_chart",
      "pair": "EUR/USD",
      "data": [
        {"date": "2026-02-01", "rate": 1.0821},
        {"date": "2026-02-02", "rate": 1.0834}
      ],
      "stats": {
        "min": 1.0798,
        "max": 1.0901,
        "mean": 1.0851,
        "stddev": 0.0031
      },
      "grid": {"col": 1, "row": 1, "col_span": 2, "row_span": 1}
    }
  ]
}
```

**Error codes**

| Code | Meaning |
|------|---------|
| 400 | Malformed request body |
| 422 | Validation error (Pydantic) |
| 429 | Session quota exhausted (`QUOTA_LIMIT_PER_SESSION` reached) |
| 500 | Connector or assembler error |
| 502 | Upstream API unreachable |

---

### `GET /api/v1/rates/history`

Fetch raw EOD historical rates for a single currency pair.

**Query parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `base` | string | Yes | Base currency code (e.g., `EUR`) |
| `quote` | string | Yes | Quote currency code (e.g., `USD`) |
| `start_date` | string (YYYY-MM-DD) | Yes | Start of range |
| `end_date` | string (YYYY-MM-DD) | Yes | End of range |

**Response — HTTP 200**

```json
{
  "base": "EUR",
  "quote": "USD",
  "rates": [
    {"date": "2026-02-01", "rate": 1.0821},
    {"date": "2026-02-02", "rate": 1.0834}
  ]
}
```

---

### `GET /api/v1/dashboards`

List all dashboards for the current session.

**Response — HTTP 200:** Array of dashboard summary objects (`id`, `name`, `dashboard_type`, `panel_count`).

---

### `POST /api/v1/dashboards`

Create a new dashboard.

**Request body:** `{"name": "My Dashboard", "dashboard_type": "single_pair_trend"}`

**Response — HTTP 201:** Full dashboard object including `id`.

---

### `GET /api/v1/dashboards/{id}`

Retrieve a dashboard by ID including all panel configurations.

---

### `PATCH /api/v1/dashboards/{id}`

Update dashboard name or type.

---

### `DELETE /api/v1/dashboards/{id}`

Delete a dashboard and all its panels.

---

### `POST /api/v1/dashboards/{id}/panels`

Add a panel to an existing dashboard.

---

### `DELETE /api/v1/dashboards/{id}/panels/{panel_id}`

Remove a panel from a dashboard.

---

### `GET /api/v1/dashboards/{id}/layout`

Return the CSS Grid layout descriptor for all panels in a dashboard.

---

### `GET /api/v1/quota`

Return current session quota usage.

**Response — HTTP 200**

```json
{
  "used": 42,
  "limit": 100,
  "remaining": 58
}
```

---

### `GET /api/v1/currencies`

Return the list of supported ISO 4217 currency codes.

**Response — HTTP 200:** `{"currencies": ["USD", "EUR", "GBP", ...]}`

---

## Contradictions and Gaps Found

| ID | Source | Finding |
|----|--------|---------|
| CONTRA-01 | `team_context.md` vs `data_design.md` | An earlier version of `team_context.md` stated the free tier requires no API key. The correct position (confirmed in `data_design.md` and project memory) is that `EXCHANGERATE_API_KEY` **is required** even on the free tier. This guide follows the correct position. |
| GAP-01 | `architecture_design.md` | The GPT-4o system prompt is referenced but not yet defined in `agent/agent.py`. Tone, refusal behaviour, and scope constraints are undocumented. The agent specialist must define and publish the system prompt. |
| GAP-02 | `product_documentation.md` | Historical rate availability on the exchangerate.host free tier is unconfirmed. If the `/historical` endpoint requires a paid plan, Feature 02 historical panels will not function without upgrading. This guide documents the feature as designed but notes the caveat in Troubleshooting (Section 6). |
| GAP-03 | `architecture_design.md` | MockConnector error injection API (`error_pairs` constructor arg) is listed as a high-priority open action item but is not yet implemented. Tests requiring error-path coverage cannot run until this is added. |

---

*End of AI Market Studio User Guide & Developer Guide.*





