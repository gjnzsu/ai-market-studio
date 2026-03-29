# AI Market Studio — Product Documentation

> **Version:** 2.1
> **Date:** 2026-03-27
> **Status:** Active
> **Scope:** FX Rate Trend Dashboard (Feature 02) — Delivered

---

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [User Stories — FX Dashboard](#2-user-stories--fx-dashboard)
3. [API Contract — New Endpoints](#3-api-contract--new-endpoints)
4. [Dashboard Type Definitions](#4-dashboard-type-definitions)
5. [Panel Type Definitions](#5-panel-type-definitions)
6. [Multi-Panel Layout Specification](#6-multi-panel-layout-specification)
7. [Gaps, Risks, and Constraints](#7-gaps-risks-and-constraints)
8. [Roadmap](#8-roadmap)

---

## 1. Product Vision

AI Market Studio is a conversational FX market data platform. Feature 01 delivered real-time single-pair rate queries via chat. Feature 02 extends the product with a **visual FX Rate Trend Dashboard**: users can create dashboards composed of multiple independent panels, each displaying historical or live FX data in a chosen visualization format. Users may switch between dashboard types (single-pair trend, multi-pair comparison, currency heatmap) without losing their panel configuration.

**Target Users:** FX traders, finance analysts, treasury teams who need rapid visual context alongside conversational queries.

---

## 2. User Stories — FX Dashboard

### US-01 — Historical Rate Query for a Currency Pair

**As a** finance analyst,
**I want to** query the historical exchange rate for a specific currency pair over a chosen date range,
**So that** I can identify rate trends and support trading decisions.

**Acceptance Criteria:**
- AC-01.1: User can specify a base currency, quote currency, start date, and end date.
- AC-01.2: System returns daily closing rates for each calendar day in the range (gaps filled with prior-day rate where source data is missing).
- AC-01.3: Date range is capped at **7 calendar days** per request by default for free-tier PoC (configurable via `MAX_HISTORICAL_DAYS` env var). Rationale: free tier only supports single-date `/historical` calls (1 call/day); a 30-day, 3-pair dashboard = 90 calls, exhausting the monthly quota in one request. Production/demo use with ranges >7 days requires a paid exchangerate.host plan.
- AC-01.4: Rates for cross-pairs (non-USD base/quote) are computed via USD triangulation using single-date `/historical` calls (free tier): fetch USD/base + USD/quote for each date (2 calls/day). For a 7-day cross-rate panel = 14 calls. Series-level `/timeseries` triangulation (2 calls total) is available on paid plans only and MUST be used when `EXCHANGERATE_PLAN=paid`. Cache stores derived cross-rate under `(base, quote, date)` key. Response labels method as `"source": "triangulated"`.
- AC-01.5: If the requested range would exceed the quota safety threshold, the API returns HTTP 429 with a human-readable message before making any external calls.
- AC-01.6: Historical data is cached by (base, quote, date) triplet for the session to avoid duplicate external calls.

---

### US-02 — Create a Dashboard

**As a** user,
**I want to** create a named dashboard and choose its type,
**So that** I can organize my FX analysis in a structured, reusable workspace.

**Acceptance Criteria:**
- AC-02.1: User can create a dashboard by providing a name (1–80 chars) and a dashboard type (`single_pair_trend` | `multi_pair_comparison` | `currency_heatmap`).
- AC-02.2: On creation, the dashboard is assigned a unique ID and is immediately accessible.
- AC-02.3: Dashboard type constrains which panel types are valid within it (see §4).
- AC-02.4: A user may have up to **10 dashboards** in a session; exceeding this returns HTTP 422.
- AC-02.5: Dashboards persist for the lifetime of the browser session (no server-side persistence required for PoC).
- AC-02.6: User can list all their dashboards with name, type, panel count, and last-updated timestamp.

---

### US-03 — Add Panels to a Dashboard

**As a** analyst,
**I want to** add multiple independent data panels to a dashboard,
**So that** I can view different FX data side-by-side without creating separate dashboards.

**Acceptance Criteria:**
- AC-03.1: User can add a panel to an existing dashboard by specifying panel type, currency pair(s), date range, and display options.
- AC-03.2: Each panel is independently configured — different pairs, different date ranges, different chart types are allowed within the same dashboard.
- AC-03.3: A dashboard supports **1–6 panels**; attempting to add a 7th returns HTTP 422.
- AC-03.4: Panels are assigned a stable integer position (1–6) within the dashboard; adding a panel appends to the next available position.
- AC-03.5: Removing a panel preserves the positions of remaining panels (no re-numbering).
- AC-03.6: Each panel independently re-fetches its data when the user triggers a refresh; panels do not share data state.

---

### US-04 — Switch Dashboard Type

**As a** user,
**I want to** switch the type of an existing dashboard,
**So that** I can change the visualization mode without rebuilding the dashboard from scratch.

**Acceptance Criteria:**
- AC-04.1: User can change dashboard type via a PATCH request.
- AC-04.2: If any existing panels are incompatible with the new type, those panels are **flagged** (status `incompatible`) but NOT silently deleted — user must explicitly remove them or the switch is rejected (validation mode: `strict` | `flag`).
- AC-04.3: Default validation mode is `strict`: type switch is rejected (HTTP 409) if incompatible panels exist.
- AC-04.4: With `validation_mode=flag`, the switch proceeds and incompatible panels are marked; they render a placeholder with an explanation.
- AC-04.5: Dashboard type switch is reflected immediately in the dashboard metadata response.

---

### US-05 — View Multi-Panel Dashboard Layout

**As a** user,
**I want to** see all panels in a dashboard rendered in a grid layout,
**So that** I can compare multiple FX data views at a glance.

**Acceptance Criteria:**
- AC-05.1: Dashboard layout API returns all panels with their data, position, and render hints in a single response.
- AC-05.2: Layout is described as a grid: 1-panel = full width; 2-panels = 2-col row; 3–4 panels = 2×2 grid; 5–6 panels = 2×3 grid. Frontend renders accordingly.
- AC-05.3: Each panel's data payload is included inline in the layout response (no second round-trip per panel).
- AC-05.4: If a panel's data fetch fails, that panel's entry includes `"status": "error"` and an error message; other panels are unaffected.
- AC-05.5: Layout response includes a `quota_used` field showing estimated external API calls consumed this session.

---

### US-06 — Quota-Aware Data Fetching

**As a** platform operator,
**I want to** enforce hard limits on external API calls,
**So that** the free-tier quota (100 req/month) is not exhausted by a single user session.

**Acceptance Criteria:**
- AC-06.1: Backend tracks a session-level counter of external API calls made to exchangerate.host.
- AC-06.2: A configurable `QUOTA_LIMIT_PER_SESSION` env var caps external calls per session (default: 20).
- AC-06.3: When the session quota is reached, all subsequent external-call-requiring endpoints return HTTP 429 with `{"error": "quota_exceeded", "session_calls": N, "limit": M}`.
- AC-06.4: MockConnector calls do NOT increment the quota counter.
- AC-06.5: The `/api/v1/quota` endpoint returns current session call count and limit.

---

## 3. API Contract — New Endpoints

All endpoints are prefixed `/api/v1`. Request and response bodies are JSON. All timestamps are ISO 8601 UTC.

### 3.1 Historical Rates

#### `GET /api/v1/rates/history`

Fetch daily historical rates for a currency pair.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `base` | string | Yes | ISO 4217 base currency (e.g. `USD`) |
| `quote` | string | Yes | ISO 4217 quote currency (e.g. `EUR`) |
| `start_date` | string (YYYY-MM-DD) | Yes | Inclusive start date |
| `end_date` | string (YYYY-MM-DD) | Yes | Inclusive end date (max 90 days from start) |

**Response 200:**

```json
{
  "base": "USD",
  "quote": "EUR",
  "start_date": "2026-01-01",
  "end_date": "2026-03-01",
  "source": "direct",
  "rates": [
    {"date": "2026-01-01", "rate": 0.9212},
    {"date": "2026-01-02", "rate": 0.9198}
  ],
  "quota_used": 3
}
```

`source` values: `"direct"` | `"triangulated"` | `"mock"`

**Error Responses:**

| HTTP | Code | Condition |
|------|------|-----------|
| 400 | `invalid_date_range` | end_date < start_date or range > 90 days |
| 400 | `invalid_currency` | Unrecognized ISO 4217 code |
| 429 | `quota_exceeded` | Session or global quota reached |
| 503 | `upstream_error` | exchangerate.host unreachable |

---

### 3.2 Dashboard Management

#### `POST /api/v1/dashboards`

Create a new dashboard.

**Request Body:**

```json
{
  "name": "My FX View",
  "dashboard_type": "multi_pair_comparison"
}
```

**Response 201:**

```json
{
  "dashboard_id": "dash_abc123",
  "name": "My FX View",
  "dashboard_type": "multi_pair_comparison",
  "panels": [],
  "created_at": "2026-03-26T10:00:00Z",
  "updated_at": "2026-03-26T10:00:00Z"
}
```

---

#### `GET /api/v1/dashboards`

List all dashboards in the current session.

**Response 200:**

```json
{
  "dashboards": [
    {
      "dashboard_id": "dash_abc123",
      "name": "My FX View",
      "dashboard_type": "multi_pair_comparison",
      "panel_count": 2,
      "updated_at": "2026-03-26T10:05:00Z"
    }
  ]
}
```

---

#### `GET /api/v1/dashboards/{dashboard_id}`

Get dashboard metadata (no panel data).

**Response 200:** Full dashboard object as in POST response, with `panels` array containing panel metadata (no data payloads).

---

#### `PATCH /api/v1/dashboards/{dashboard_id}`

Update dashboard name or type.

**Request Body (all fields optional):**

```json
{
  "name": "Renamed View",
  "dashboard_type": "currency_heatmap",
  "validation_mode": "strict"
}
```

**Response 200:** Updated dashboard object.

**Error 409** (strict mode, incompatible panels):

```json
{
  "error": "incompatible_panels",
  "incompatible_panel_ids": ["panel_1", "panel_3"],
  "message": "Remove or reconfigure these panels before switching type."
}
```

---

#### `DELETE /api/v1/dashboards/{dashboard_id}`

Delete a dashboard and all its panels.

**Response 204:** No content.

---

### 3.3 Panel Management

#### `POST /api/v1/dashboards/{dashboard_id}/panels`

Add a panel to a dashboard.

**Request Body:**

```json
{
  "panel_type": "line_chart",
  "title": "USD/EUR — Jan to Mar 2026",
  "config": {
    "pairs": [{"base": "USD", "quote": "EUR"}],
    "start_date": "2026-01-01",
    "end_date": "2026-03-01",
    "display_options": {
      "show_legend": true,
      "y_axis_label": "Rate"
    }
  }
}
```

**Response 201:**

```json
{
  "panel_id": "panel_1",
  "dashboard_id": "dash_abc123",
  "position": 1,
  "panel_type": "line_chart",
  "title": "USD/EUR — Jan to Mar 2026",
  "status": "ok",
  "config": {}
}
```

**Error 422** (max panels exceeded or incompatible panel type for dashboard type).

---

#### `DELETE /api/v1/dashboards/{dashboard_id}/panels/{panel_id}`

Remove a panel.

**Response 204:** No content.

---

### 3.4 Dashboard Layout (Render)

#### `GET /api/v1/dashboards/{dashboard_id}/layout`

Return all panel data in a single response for rendering.

**Response 200:**

```json
{
  "dashboard_id": "dash_abc123",
  "dashboard_type": "multi_pair_comparison",
  "grid": "2col",
  "quota_used": 5,
  "panels": [
    {
      "panel_id": "panel_1",
      "position": 1,
      "panel_type": "line_chart",
      "title": "USD/EUR",
      "status": "ok",
      "data": {
        "labels": ["2026-01-01", "2026-01-02"],
        "series": [{"pair": "USD/EUR", "values": [0.921, 0.919]}]
      }
    }
  ]
}
```

`grid` values: `"full"` (1 panel) | `"2col"` (2 panels) | `"2x2"` (3–4) | `"2x3"` (5–6)

---

### 3.5 Quota Endpoint

#### `GET /api/v1/quota`

**Response 200:**

```json
{
  "session_calls": 5,
  "limit": 20,
  "remaining": 15
}
```

---

## 4. Dashboard Type Definitions

| Dashboard Type | ID | Description | Allowed Panel Types |
|---|---|---|---|
| Single-Pair Trend | `single_pair_trend` | Deep analysis of one currency pair over time. One pair per panel. | `line_chart`, `bar_chart`, `stats_summary` |
| Multi-Pair Comparison | `multi_pair_comparison` | Side-by-side comparison of up to 6 pairs. Each panel shows one or more pairs. | `line_chart`, `bar_chart`, `stats_summary` |
| Currency Heatmap | `currency_heatmap` | Grid showing pairwise rate changes (% change over period) for a currency set. | `heatmap_cell`, `stats_summary` |

### Single-Pair Trend
- Panels must reference exactly one currency pair.
- Suitable for identifying support/resistance, trend direction, volatility spikes.
- Date range per panel: 1–31 days (default `MAX_HISTORICAL_DAYS`).

### Multi-Pair Comparison
- Each panel may reference 1–4 pairs plotted on the same chart.
- Useful for basket analysis (e.g. USD vs EUR, GBP, JPY, AUD simultaneously).
- Date ranges per panel are independent.

### Currency Heatmap
- User selects a currency set (3–6 currencies); backend computes all pairwise % changes.
- Each cell = one pair. Layout is auto-generated (NxN grid minus diagonal).
- A 5-currency heatmap = 5×4/2 = **10 unique pairs** (symmetric matrix, no diagonal). Cold: up to 10 upstream calls; warm (cache hit): 0 calls. See §7 GAP-08 and GAP-12.
- Date range applies to the whole dashboard (single range, not per-panel).

## 5. Panel Type Definitions

| Panel Type | ID | Description | Compatible Dashboard Types |
|---|---|---|---|
| Line Chart | `line_chart` | Time-series line plot of rate(s) over date range | `single_pair_trend`, `multi_pair_comparison` |
| Bar Chart | `bar_chart` | Daily rate bars for a pair; useful for volatility view | `single_pair_trend`, `multi_pair_comparison` |
| Stats Summary | `stats_summary` | Text/numeric panel: min, max, avg, % change over period | All types |
| Heatmap Cell | `heatmap_cell` | Single cell in a heatmap grid; % change for one pair | `currency_heatmap` |

### Panel Config Fields by Type

**line_chart / bar_chart:**
```
pairs:         array of {base, quote}   required  1–4 pairs
start_date:    YYYY-MM-DD               required
end_date:      YYYY-MM-DD               required
display_options:
  show_legend: boolean                  default true
  y_axis_label: string                  default "Rate"
```

**stats_summary:**
```
pairs:         array of {base, quote}   required  1–4 pairs
start_date:    YYYY-MM-DD               required
end_date:      YYYY-MM-DD               required
metrics:       array of enum            default ["min","max","avg","pct_change"]
```

**heatmap_cell:**
```
base:          string                   required
quote:         string                   required
(date range inherited from dashboard)
```

## 6. Multi-Panel Layout Specification

The layout is determined server-side based on panel count and returned as the `grid` field in the layout response.

| Panel Count | Grid Value | Description |
|---|---|---|
| 1 | `full` | Single panel, full viewport width |
| 2 | `2col` | Two panels side-by-side, equal width |
| 3–4 | `2x2` | Two rows, two columns (4th slot empty if 3 panels) |
| 5–6 | `2x3` | Two rows, three columns |

### Layout Rules
- Panels are placed in position order (1 = top-left, filling left-to-right, top-to-bottom).
- Empty slots in a grid are rendered as blank placeholders (not hidden).
- Frontend must handle `"status": "error"` and `"status": "incompatible"` panel states gracefully.
- No drag-and-drop reordering in PoC; positions are fixed at creation time.
- The frontend uses CSS Grid (no external JS libraries). Grid template is driven by `grid` value.

### Frontend Rendering Contract
- One HTTP call: `GET /api/v1/dashboards/{id}/layout` fetches all panel data.
- Frontend does not make per-panel HTTP calls.
- **Chart panel data shape (confirmed):**
  ```json
  {"labels": ["2026-03-01", "..."], "series": [{"pair": "USD/EUR", "values": [0.9234, null, ...]}]}
  ```
  `labels` = union of all dates across pairs. `values` entries are `null` for weekend/holiday gaps. Frontend must render nulls as gaps (no interpolation).
- **Stats panel data shape (confirmed):**
  ```json
  {"pair": "USD/EUR", "metrics": {"min": 0.9101, "max": 0.9312, "avg": 0.9205, "pct_change": -0.39}}
  ```
  `pct_change` = ((last - first) / first) × 100.
- Both shapes are produced by the backend API layer from the connector's raw `[{"date": "YYYY-MM-DD", "rate": float}]` output. The connector does not compute stats or serialize chart data.

## 7. Gaps, Risks, and Constraints

| ID | Risk / Gap | Severity | Mitigation |
|---|---|---|---|
| GAP-08 | **100 req/month quota (CONFIRMED CRITICAL)**: Free tier = single-date `/historical` only (1 call/day/pair). A 7-day, 3-pair dashboard = 21 calls cold. A 30-day, 3-pair dashboard = 90 calls — exhausts monthly quota in one request. EOD rates only; no intraday granularity. | CRITICAL | (1) Default `MAX_HISTORICAL_DAYS=7` for free-tier PoC. (2) Session quota limit via `QUOTA_LIMIT_PER_SESSION` (default 20). (3) Mandate `USE_MOCK_CONNECTOR=true` for all development, CI, and demos. (4) In-memory cache with 24h TTL keyed by (base, quote, date) — repeat loads cost 0 calls. (5) Ranges >7 days or production use requires paid exchangerate.host plan ($14.99/month Basic). Document prominently in user guide and UI. |
| GAP-09 | **No external JS libraries**: All charting must use native Canvas API or SVG. No Chart.js, D3, or similar. This significantly increases frontend effort for heatmap rendering. | HIGH | Scope heatmap to CSS-colored table cells (% change as background color) rather than a true chart. Line/bar charts use Canvas API with minimal hand-rolled renderer. |
| GAP-10 | **No server-side persistence**: Dashboards are session-only (in-memory). A page refresh destroys all dashboards. | MEDIUM | Document clearly in user guide. Post-PoC: add localStorage persistence or a lightweight backend store. |
| GAP-11 | **Historical endpoint availability on free tier (CONFIRMED)**: `/timeseries` endpoint requires Basic paid plan ($14.99/month). Free tier supports single-date `/historical` only — 1 call per day per pair. | HIGH (confirmed) | Connector MUST use `/historical` loop on free tier. `EXCHANGERATE_PLAN` env var (`free`\|`paid`) controls endpoint selection. Series-level triangulation only available when `EXCHANGERATE_PLAN=paid`. |
| GAP-12 | **Historical cross-rate triangulation cost (UPDATED)**: Free tier = 2 calls/day per cross-rate pair (USD/base + USD/quote via `/historical`). A 7-day EUR/GBP panel = 14 calls cold. Paid tier = 2 calls total via `/timeseries` series-level triangulation. | MEDIUM (free tier) / LOW (paid tier) | Free tier: cross-rate panels reduce effective pair capacity by 50%. Warn user in UI when adding a cross-rate panel. Paid tier: use series-level triangulation (`EXCHANGERATE_PLAN=paid`). Cache always stores derived cross-rate under `(base, quote, date)` — warm cost = 0. |
| GAP-13 | **No authentication**: All dashboard and rate endpoints are unauthenticated. Any user on the network can read or delete any dashboard by ID. | LOW (PoC only) | Document as known PoC shortcut. Add to Phase 3 hardening backlog. |
| GAP-14 | **GPT-4o system prompt not defined**: The agent system prompt is still an open action item from Feature 01. Feature 02 adds dashboard context (e.g. user asking "add a EUR/USD panel") that the agent must handle. | HIGH | Define system prompt before Feature 02 agent integration. Out of scope for dashboard API but blocks conversational dashboard control. |

## 8. Roadmap

| Priority | Theme | Features |
|----------|-------|----------|
| **P0 — Done** | Foundation | Chat assistant, spot & historical FX rates, conversational dashboard, market news, GKE deployment |
| **P1 — Awareness** | Market Intelligence | F7: Market Insight Summary — AI-generated "why is EUR/USD moving?" commentary from news + rate data; F3: Market News (delivered) |
| **P2 — Productivity** | Output Generation | F9: PPT / Excel / PDF report generation; F8: Email sending of insights and reports |
| **P3 — Intelligence** | Research | F5: Web search integration for live market context; F4: Research report generation via RAG pipeline over internal documents |
| **P4 — Data Breadth** | Data & Collaboration | F1: Multi-source market data connectors; F6: Sales/trader commentary capture and retrieval; F12: Scheduled report function |
| **P5 — Advanced** | Platform | F10: Custom agent creation; F11: OCR / document ingestion (scanned reports, PDFs) |

### Delivered Detail

#### Feature 01 — FX Chat Assistant (PoC)
- Natural-language FX spot rate queries via chat
- GPT-4o function calling with 3 tools
- MockConnector + 90% coverage gate
- Single HTML frontend, no build step

#### Feature 02 — FX Rate Historical Data (2026-03-27)
- `POST /api/rates/historical` — daily FX rates with in-memory LRU cache (TTL=300s, max 200 entries)
- `POST /api/dashboard` — batch panel fetch, reuses cache across panels
- Line trend, bar comparison, and stat summary panel types
- `USE_MOCK_CONNECTOR` env var; `trust_env=False` httpx fix for Windows proxy

#### Feature 03 — Market News (2026-03-29)
- `get_fx_news` GPT-4o tool; inline news cards in chat bubble
- Free RSS feeds: BBC Business, Investing.com FX, FXStreet — no paid API key
- `USE_MOCK_NEWS_CONNECTOR` decoupled from rate connector flag
- MockNewsConnector for all tests (8+ deterministic items)

#### Feature 04 — Conversational Dashboard (2026-03-28)
- LLM detects chart/visualize/show intent and calls `generate_dashboard` tool
- Inline Chart.js chart renders inside the chat bubble — no tab switching
- Supports line trend (time series) and bar comparison chart types
- UI simplified to single-pane chat; dashboard tab removed

---

*End of product documentation.*
