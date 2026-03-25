# FX Rate Trend Dashboard — Implementation Plan

**Author:** Full Stack Engineer Agent
**Date:** 2026-03-26
**Feature:** Feature 02 — FX Rate Trend Dashboard
**Status:** Draft for Tech Lead Review

---

## 0. Overview

This plan adds a historical FX Rate Trend Dashboard to the existing AI Market Studio PoC.
The dashboard renders multiple panel types (line trend, bar comparison, summary stats)
arranged in a configurable grid, driven by new backend endpoints and an in-memory
`RateCache`. All changes are strictly additive — Feature 01 (chat interface) is untouched.

Test coverage target: 90% gate (existing). All new tests use `MockConnector`.
No external JS libraries. Single `frontend/index.html` file.

---

## 1. Backend Changes

### 1.1 `backend/connectors/base.py` — Add abstract method

Append one new `@abstractmethod` to `MarketDataConnector`:

```python
@abstractmethod
async def get_historical_rates(
    self,
    base: str,
    targets: list[str],
    start_date: str,   # ISO-8601 "YYYY-MM-DD"
    end_date: str,     # ISO-8601 "YYYY-MM-DD"
) -> dict[str, dict[str, float]]:
    """
    Return daily closing rates for each target currency.

    Returns:
        {
            "2025-01-01": {"EUR": 0.92, "GBP": 0.79},
            "2025-01-02": {"EUR": 0.921, "GBP": 0.791},
            ...
        }
    Raises:
        RateFetchError: on network / API failure.
        UnsupportedPairError: if base or any target is unsupported.
    """
```

Existing methods (`get_exchange_rate`, `get_exchange_rates`, `list_supported_currencies`) are unchanged.


---

### 1.2 `backend/connectors/mock_connector.py` — Implement `get_historical_rates`

Add to `MockConnector`:

```python
import math
from datetime import date as _date, timedelta

async def get_historical_rates(
    self,
    base: str,
    targets: list[str],
    start_date: str,
    end_date: str,
) -> dict[str, dict[str, float]]:
    """
    Generate deterministic synthetic daily rates.

    Algorithm per (base, target, day_index):
        seed      = abs(hash(base.upper() + target.upper())) % 10_000
        base_rate = (seed / 10_000) * 1.5 + 0.5      # in (0.5, 2.0)
        delta     = math.sin(day_index * 0.3) * 0.02  # gentle oscillation
        rate      = round(base_rate + delta, 6)

    Respects error_pairs / unsupported_pairs injection.
    All dates in [start_date, end_date] inclusive are returned.
    """
    base = base.upper()
    result: dict[str, dict[str, float]] = {}
    start = _date.fromisoformat(start_date)
    end   = _date.fromisoformat(end_date)
    day_count = (end - start).days + 1
    for i in range(day_count):
        day = start + timedelta(days=i)
        day_str = day.isoformat()
        result[day_str] = {}
        for target in targets:
            t = target.upper()
            pair_key = f"{base}{t}"
            if pair_key in self._error_pairs:
                from backend.connectors.base import RateFetchError
                raise RateFetchError(f"Simulated error for {base}/{t}")
            if pair_key in self._unsupported_pairs:
                from backend.connectors.base import UnsupportedPairError
                raise UnsupportedPairError(f"{base}/{t} not supported (mock)")
            seed = abs(hash(base + t)) % 10_000
            base_rate = (seed / 10_000) * 1.5 + 0.5
            delta = math.sin(i * 0.3) * 0.02
            result[day_str][t] = round(base_rate + delta, 6)
    return result
```

**Notes:** Uses only stdlib. `hash()` is deterministic within a Python process (PYTHONHASHSEED=0 in tests for full reproducibility — see conftest note in §3).


---

### 1.3 `backend/connectors/exchangerate_host.py` — Implement `get_historical_rates`

**CONFIRMED (OQ-1 resolved):** `/timeseries` is NOT available on the free tier.
Implementation uses sequential `/historical` calls, one per day, **capped at 7 days max**.
The `HistoricalRatesRequest` validator must enforce `MAX_HISTORICAL_DAYS=7`.

Add to `ExchangeRateHostConnector`:

```python
from datetime import date as _date, timedelta

async def get_historical_rates(
    self,
    base: str,
    targets: list[str],
    start_date: str,
    end_date: str,
) -> dict[str, dict[str, float]]:
    """
    Fetch daily closing rates via sequential /historical calls.

    IMPORTANT: /timeseries is not available on the free tier.
    Makes one API call per day in [start_date, end_date].
    Caller must enforce max 7 days (7 calls) to stay within 100 req/month.

    URL per day: https://api.exchangerate.host/historical
    Params: access_key, base, symbols (comma-joined), date
    Raises RateFetchError on any non-200 or missing "rates" key.
    """
    base = base.upper()
    symbols = ",".join(t.upper() for t in targets)
    start = _date.fromisoformat(start_date)
    end   = _date.fromisoformat(end_date)
    result: dict[str, dict[str, float]] = {}
    current = start
    async with httpx.AsyncClient(timeout=10.0) as client:
        while current <= end:
            params = {
                "access_key": self._api_key,
                "base":       base,
                "symbols":    symbols,
                "date":       current.isoformat(),
            }
            resp = await client.get(
                "https://api.exchangerate.host/historical", params=params
            )
            if resp.status_code != 200:
                raise RateFetchError(f"historical HTTP {resp.status_code} for {current}")
            body = resp.json()
            if not body.get("success") or "rates" not in body:
                raise RateFetchError(f"historical API error for {current}: {body.get('error')}")
            result[current.isoformat()] = body["rates"]
            current += timedelta(days=1)
    return result
```

**Quota impact:** 1 call per day × N days × M target currencies = N calls total (symbols are
batched per day). A 7-day, 3-target dashboard = **7 API calls**. Monthly budget: ~14 dashboard
loads before exhausting the 100 req/month free tier. Cache hits do not consume quota.

---

### 1.4 `backend/models.py` — New Pydantic models

Append after existing `ChatResponse` (do not modify existing models):

```python
from typing import Literal
from pydantic import field_validator

class HistoricalRatesRequest(BaseModel):
    base:       str       = Field(..., min_length=3, max_length=3)
    targets:    list[str] = Field(..., min_length=1, max_length=10)
    start_date: str       = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date:   str       = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("base", "targets", mode="before")
    @classmethod
    def upper(cls, v):
        if isinstance(v, list):
            return [x.upper() for x in v]
        return v.upper()


class DailyRates(BaseModel):
    date:  str              # "YYYY-MM-DD"
    rates: dict[str, float] # {"EUR": 0.92}


class HistoricalRatesResponse(BaseModel):
    base:       str
    start_date: str
    end_date:   str
    series:     list[DailyRates]  # sorted ascending
    cached:     bool = False


class DashboardPanelConfig(BaseModel):
    panel_id:   str
    panel_type: Literal["line_trend", "bar_comparison", "stat_summary"]
    base:       str
    targets:    list[str]
    start_date: str
    end_date:   str


class DashboardConfig(BaseModel):
    dashboard_id:   str
    dashboard_type: Literal["trend", "comparison", "mixed"]
    panels: list[DashboardPanelConfig] = Field(..., min_length=1, max_length=9)


class DashboardDataResponse(BaseModel):
    dashboard_id: str
    panels: list[dict]  # {panel_id, panel_type, data: HistoricalRatesResponse}
```

---

## 4. Implementation Order

Build in this sequence to ensure each layer is testable before the next depends on it.

| Step | File(s) | Depends on | Deliverable |
|------|---------|-----------|-------------|
| 1 | `backend/connectors/base.py` | — | `get_historical_rates` abstract method |
| 2 | `backend/connectors/mock_connector.py` | Step 1 | Deterministic historical data |
| 3 | `backend/tests/unit/test_mock_connector.py` | Step 2 | Connector tests green |
| 4 | `backend/cache.py` | — | `RateCache` singleton |
| 5 | `backend/tests/unit/test_cache.py` | Step 4 | Cache tests green |
| 6 | `backend/models.py` | — | New Pydantic models |
| 7 | `backend/tests/unit/test_schemas.py` additions | Step 6 | Schema tests green |
| 8 | `backend/router.py` | Steps 1,4,6 | Two new endpoints |
| 9 | `backend/tests/e2e/test_dashboard_api.py` | Steps 2,8 | E2E tests green, 90% coverage gate passes |
| 10 | `backend/agent/tools.py` | Step 1 | `get_historical_rates` tool + dispatch |
| 11 | `backend/tests/unit/test_tools.py` additions | Step 10 | Tool dispatch tests green |
| 12 | `backend/connectors/exchangerate_host.py` | Step 1 | Live connector (manual test only) |
| 13 | `frontend/index.html` | Step 8 | Dashboard UI — tab, controls, canvas charts |

**Steps 1–11** can be completed with MockConnector only and zero live API calls.
**Step 12** requires `USE_MOCK_CONNECTOR=false` and a valid `EXCHANGERATE_API_KEY` — manual only.
**Step 13** can begin in parallel with Step 8 once the API contract (models) is finalised at Step 6.

---

## 5. Risks and Open Questions

### OQ-1 — exchangerate.host `/timeseries` on free tier — RESOLVED
**Resolution (2026-03-26):** Confirmed by Architect + Data Engineer: `/timeseries` is NOT
available on the free tier. Implementation uses sequential `/historical` calls, one per day,
capped at **7 days maximum** per request. See §1.3 for updated connector implementation.
**Quota arithmetic:** 7 days × 1 call/day = 7 calls per dashboard load. ~14 full dashboard
loads per month on the free tier before quota exhaustion. Cache hits cost 0 calls.

### OQ-2 — `hash()` non-determinism across processes
**Risk:** Python's `hash()` is randomised by default (PYTHONHASHSEED). MockConnector uses
`hash(base + target)` for rate generation. Tests asserting exact float values will fail
unless `PYTHONHASHSEED=0` is set in the test environment.
**Mitigation:** Add `PYTHONHASHSEED=0` to `pyproject.toml` `[tool.pytest.ini_options]` env,
or replace `hash()` with a stable hash (`hashlib.md5`).

### OQ-3 — `DashboardDataResponse.panels` serialisation
**Risk:** `panels: list[dict]` loses Pydantic validation on the nested `HistoricalRatesResponse`.
If the router stores a Pydantic model object inside the dict, FastAPI's JSON encoder handles it;
but explicit `model.model_dump()` calls may be needed for correct serialisation.
**Mitigation:** Change to `panels: list[PanelResult]` with a typed `PanelResult` model, or
call `.model_dump()` explicitly before appending to `panels_out`.

### OQ-4 — Canvas sizing on small viewports
**Risk:** Fixed `canvas.width=480` clips on mobile or narrow sidebar layouts.
**Mitigation:** Set canvas logical size via JS after measuring `div.clientWidth`.
Out of scope for PoC but flag for Phase 3.

### OQ-5 — Rate cache not cleared between E2E tests
**Risk:** `rate_cache` is a module-level singleton. If the FastAPI `TestClient` reuses the same
process, cache state leaks between tests, causing false cache-hit assertions.
**Mitigation:** Call `rate_cache.clear()` in a pytest `autouse` fixture in `conftest.py`.

### OQ-6 — 7-day cap enforcement (UPDATED — was 31-day)
**Risk:** Without a hard cap, a single request could exhaust the monthly quota (100 req/month)
in one go. With sequential `/historical` calls, an uncapped 30-day query = 30 API calls.
**Mitigation (mandatory):** Add a date-range validator to `HistoricalRatesRequest`:
```python
@model_validator(mode="after")
def validate_date_range(self) -> "HistoricalRatesRequest":
    from datetime import date
    start = date.fromisoformat(self.start_date)
    end   = date.fromisoformat(self.end_date)
    if (end - start).days >= settings.max_historical_days:
        raise ValueError(
            f"Date range exceeds {settings.max_historical_days}-day limit"
        )
    return self
```
Add `max_historical_days: int = 7` to `backend/config.py`.
Frontend date picker must enforce the same 7-day window client-side.

---

## 6. Files Created / Modified Summary

| File | Action | Feature 01 Impact |
|------|--------|------------------|
| `backend/connectors/base.py` | Modify — add abstract method | None (additive) |
| `backend/connectors/mock_connector.py` | Modify — add method | None |
| `backend/connectors/exchangerate_host.py` | Modify — add method | None |
| `backend/models.py` | Modify — append models | None |
| `backend/cache.py` | **New file** | None |
| `backend/router.py` | Modify — append routes + imports | None |
| `backend/agent/tools.py` | Modify — append tool def + dispatch | None |
| `backend/config.py` | Modify — add `max_historical_days` | None |
| `frontend/index.html` | Modify — add tab, dashboard section, JS | Chat preserved |
| `backend/tests/unit/test_mock_connector.py` | **New file** | — |
| `backend/tests/unit/test_cache.py` | **New file** | — |
| `backend/tests/unit/test_schemas.py` | Modify — add cases | — |
| `backend/tests/unit/test_tools.py` | Modify — add cases | — |
| `backend/tests/e2e/test_dashboard_api.py` | **New file** | — |

---

*End of implementation plan.*
---

### 1.5 `backend/cache.py` — New file (in-memory RateCache)

```python
"""
In-memory LRU cache for historical rate responses.
Key: (base, tuple(sorted(targets)), start_date, end_date)
TTL: 300 s (default). Max 200 entries (LRU eviction).
"""
from __future__ import annotations
import time
from collections import OrderedDict
from typing import Optional

_CACHE_MAX = 200


class RateCache:
    def __init__(self, ttl_seconds: int = 300, max_entries: int = _CACHE_MAX):
        self._store: OrderedDict = OrderedDict()
        self.ttl = ttl_seconds
        self.max_entries = max_entries

    def _key(self, base: str, targets: list[str], start: str, end: str) -> tuple:
        return (base.upper(), tuple(sorted(t.upper() for t in targets)), start, end)

    def get(self, base, targets, start, end) -> Optional[dict]:
        key = self._key(base, targets, start, end)
        if key not in self._store:
            return None
        ts, value = self._store[key]
        if time.monotonic() - ts > self.ttl:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return value

    def set(self, base, targets, start, end, value: dict) -> None:
        key = self._key(base, targets, start, end)
        if len(self._store) >= self.max_entries:
            self._store.popitem(last=False)
        self._store[key] = (time.monotonic(), value)

    def clear(self) -> None:
        self._store.clear()


# Module-level singleton imported by router.py
rate_cache = RateCache()
```

**Location:** `backend/cache.py` (new file, parallel to `config.py`).
**Initialisation:** Module-level singleton — no FastAPI lifespan changes needed.

---

### 1.6 `backend/router.py` — Two new endpoints

Add imports at top:
```python
from backend.cache import rate_cache
from backend.models import (
    HistoricalRatesRequest, HistoricalRatesResponse, DailyRates,
    DashboardConfig, DashboardDataResponse,
)
from backend.connectors.base import ConnectorError
```

Append two routes after the existing `/chat` route:

```python
@router.post("/rates/historical", response_model=HistoricalRatesResponse)
async def get_historical_rates(
    request: Request, body: HistoricalRatesRequest
) -> HistoricalRatesResponse:
    """
    1. Check rate_cache — return with cached=True on hit.
    2. Call connector.get_historical_rates(...).
    3. Sort date keys ascending, build list[DailyRates].
    4. Store in rate_cache.
    5. Return HistoricalRatesResponse(cached=False).
    HTTP 502 on ConnectorError, HTTP 422 on validation (automatic).
    """
    connector = request.app.state.connector
    hit = rate_cache.get(body.base, body.targets, body.start_date, body.end_date)
    if hit:
        return hit
    try:
        raw = await connector.get_historical_rates(
            body.base, body.targets, body.start_date, body.end_date
        )
    except ConnectorError as e:
        raise HTTPException(status_code=502, detail=str(e))
    series = [
        DailyRates(date=d, rates=raw[d]) for d in sorted(raw.keys())
    ]
    resp = HistoricalRatesResponse(
        base=body.base,
        start_date=body.start_date,
        end_date=body.end_date,
        series=series,
        cached=False,
    )
    rate_cache.set(body.base, body.targets, body.start_date, body.end_date, resp)
    return resp


@router.post("/dashboard", response_model=DashboardDataResponse)
async def get_dashboard_data(
    request: Request, config: DashboardConfig
) -> DashboardDataResponse:
    """
    Batch-fetch data for all panels. Reuses cache across panels that
    share the same (base, targets, dates) — protects 100 req/month quota.
    """
    connector = request.app.state.connector
    panels_out = []
    for panel in config.panels:
        hit = rate_cache.get(
            panel.base, panel.targets, panel.start_date, panel.end_date
        )
        if hit:
            panels_out.append({"panel_id": panel.panel_id,
                                "panel_type": panel.panel_type,
                                "data": hit})
            continue
        try:
            raw = await connector.get_historical_rates(
                panel.base, panel.targets, panel.start_date, panel.end_date
            )
        except ConnectorError as e:
            raise HTTPException(status_code=502, detail=str(e))
        series = [DailyRates(date=d, rates=raw[d]) for d in sorted(raw.keys())]
        resp = HistoricalRatesResponse(
            base=panel.base, start_date=panel.start_date,
            end_date=panel.end_date, series=series, cached=False,
        )
        rate_cache.set(
            panel.base, panel.targets, panel.start_date, panel.end_date, resp
        )
        panels_out.append({"panel_id": panel.panel_id,
                           "panel_type": panel.panel_type,
                           "data": resp})
    return DashboardDataResponse(
        dashboard_id=config.dashboard_id, panels=panels_out
    )
```

**Note:** Router prefix is `/api` (set in `main.py`), so full paths are `/api/rates/historical` and `/api/dashboard`.

---

### 1.7 `backend/agent/tools.py` — New tool definition

Append to `TOOL_DEFINITIONS` list:

```python
{
    "type": "function",
    "function": {
        "name": "get_historical_rates",
        "description": (
            "Retrieve historical daily FX rates for a base currency against one or "
            "more target currencies over a date range. Use when the user asks about "
            "rate trends, historical performance, or wants to compare rates over time."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "base": {"type": "string", "description": "ISO 4217 base currency, e.g. USD"},
                "targets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of target currency codes"
                },
                "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "end_date":   {"type": "string", "description": "End date YYYY-MM-DD"},
            },
            "required": ["base", "targets", "start_date", "end_date"],
        },
    },
},
```

Also add a dispatch branch in `dispatch_tool`:

```python
elif tool_name == "get_historical_rates":
    return await connector.get_historical_rates(
        base=tool_args["base"],
        targets=tool_args["targets"],
        start_date=tool_args["start_date"],
        end_date=tool_args["end_date"],
    )
```

---

## 2. Frontend Changes (`frontend/index.html`)

All changes are additive inside the single HTML file. Feature 01 chat UI is preserved.

### 2.1 Tab Navigation

Add a tab bar in `<header>` (after the existing `<h1>`):

```html
<nav id="tab-bar">
  <button class="tab active" data-tab="chat">Chat</button>
  <button class="tab" data-tab="dashboard">Dashboard</button>
</nav>
```

CSS: `.tab.active` has `border-bottom: 2px solid #a5b4fc`. Tab switch hides/shows
`#chat-section` and `#dashboard-section` via `display: none / flex`.

### 2.2 Dashboard Section Layout

```html
<section id="dashboard-section" style="display:none; flex-direction:column; flex:1">
  <div id="dashboard-controls"><!-- config form --></div>
  <div id="panel-grid"><!-- panels injected here --></div>
</section>
```

`#panel-grid` uses CSS Grid: `grid-template-columns: repeat(auto-fit, minmax(360px, 1fr))`.
Each panel is a `<div class="panel">` containing a `<canvas>` or stats table.

### 2.3 Dashboard Config Form

Controls inside `#dashboard-controls`:

| Control | Element | Notes |
|---|---|---|
| Dashboard type | `<select id="dash-type">` | trend / comparison / mixed |
| Base currency | `<select id="dash-base">` | populated from `/api/chat` currencies list |
| Target currencies | `<select id="dash-targets" multiple>` | max 5 selected |
| Start date | `<input type="date" id="dash-start">` | defaults to 30 days ago |
| End date | `<input type="date" id="dash-end">` | defaults to today |
| Load button | `<button id="dash-load">Load Dashboard</button>` | triggers fetch |
| Add panel button | `<button id="dash-add-panel">+ Panel</button>` | appends panel config |

### 2.4 Dashboard State (Vanilla JS)

```js
// Module-level state
let dashboardPanels = [];  // array of DashboardPanelConfig objects
let dashboardType  = 'trend';

// Each panel config:
// { panel_id, panel_type, base, targets[], start_date, end_date }

function addPanel(panelType) {
  const id = 'panel-' + Date.now();
  dashboardPanels.push({
    panel_id:   id,
    panel_type: panelType,
    base:       document.getElementById('dash-base').value,
    targets:    getSelectedTargets(),
    start_date: document.getElementById('dash-start').value,
    end_date:   document.getElementById('dash-end').value,
  });
}

function removePanel(panelId) {
  dashboardPanels = dashboardPanels.filter(p => p.panel_id !== panelId);
  document.getElementById(panelId)?.remove();
}
```

State is ephemeral (page lifetime only). No localStorage in PoC scope.

### 2.5 Fetching Dashboard Data

```js
const DASHBOARD_API = '/api/dashboard';

async function loadDashboard() {
  if (!dashboardPanels.length) return;
  const body = {
    dashboard_id:   'dash-' + Date.now(),
    dashboard_type: dashboardType,
    panels:         dashboardPanels,
  };
  const res = await fetch(DASHBOARD_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) { showDashError(await res.text()); return; }
  const data = await res.json();
  renderDashboard(data);
}
```

### 2.6 Chart Rendering (Canvas 2D)

All charts use `<canvas>` elements — no external libraries.

#### `renderLineChart(canvas, series, targets)`
- Inputs: `canvas` element, `series` (list of `{date, rates}`), `targets` (string[]).
- Axes: X = dates (evenly spaced), Y = rate range auto-scaled with 5% padding.
- One polyline per target currency, distinct colours from a fixed palette.
- X-axis tick labels: every 7th date label to avoid crowding.
- Legend: currency code + colour swatch, drawn in top-right corner of canvas.

#### `renderBarChart(canvas, series, targets)`
- Groups bars by date (one group per date, one bar per target).
- Suitable for `bar_comparison` panel type.
- For ranges > 14 days, aggregate to weekly averages before rendering.

#### `renderStatSummary(container, series, target)`
- No canvas — renders a `<table>` inside the panel `<div>`.
- Rows: Min rate, Max rate, Average rate, Start rate, End rate, % Change.
- Calculated client-side from the series data.

### 2.7 Panel Rendering

```js
function renderDashboard(data) {
  const grid = document.getElementById('panel-grid');
  grid.innerHTML = '';
  for (const panel of data.panels) {
    const div = document.createElement('div');
    div.className = 'panel';
    div.id = panel.panel_id;
    if (panel.panel_type === 'line_trend') {
      const canvas = document.createElement('canvas');
      canvas.width = 480; canvas.height = 280;
      div.appendChild(canvas);
      renderLineChart(canvas, panel.data.series, Object.keys(panel.data.series[0]?.rates || {}));
    } else if (panel.panel_type === 'bar_comparison') {
      const canvas = document.createElement('canvas');
      canvas.width = 480; canvas.height = 280;
      div.appendChild(canvas);
      renderBarChart(canvas, panel.data.series, Object.keys(panel.data.series[0]?.rates || {}));
    } else if (panel.panel_type === 'stat_summary') {
      renderStatSummary(div, panel.data.series,
        Object.keys(panel.data.series[0]?.rates || {})[0]);
    }
    const removeBtn = document.createElement('button');
    removeBtn.textContent = 'Remove';
    removeBtn.onclick = () => removePanel(panel.panel_id);
    div.appendChild(removeBtn);
    grid.appendChild(div);
  }
}
```

### 2.8 CSS additions (inside existing `<style>` block)

```css
#tab-bar { display: flex; gap: 0.5rem; margin-left: auto; }
.tab {
  background: none; border: none; color: #94a3b8;
  font-size: 0.9rem; cursor: pointer; padding: 0.4rem 0.8rem;
  border-bottom: 2px solid transparent;
}
.tab.active { color: #a5b4fc; border-bottom-color: #a5b4fc; }
#dashboard-controls {
  display: flex; flex-wrap: wrap; gap: 0.75rem;
  padding: 1rem 1.5rem; background: #1a1d27;
  border-bottom: 1px solid #2d3148;
}
#panel-grid {
  flex: 1; overflow-y: auto; padding: 1rem 1.5rem;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 1rem; align-content: start;
}
.panel {
  background: #1e2235; border: 1px solid #2d3148;
  border-radius: 10px; padding: 1rem; position: relative;
}
.panel canvas { display: block; width: 100%; height: auto; }
.panel table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.panel td, .panel th { padding: 0.4rem 0.6rem; border-bottom: 1px solid #2d3148; }
.panel button.remove-panel {
  position: absolute; top: 0.5rem; right: 0.5rem;
  background: none; border: none; color: #64748b; cursor: pointer;
  font-size: 0.8rem;
}
```

---

## 3. Test Stubs

All tests live under `backend/tests/`. All use `MockConnector`.
Add `PYTHONHASHSEED=0` to pytest invocation (`pytest -p no:randomly` or via `pyproject.toml`)
so that `hash()` is deterministic for MockConnector rate generation.

### 3.1 `backend/tests/unit/test_mock_connector.py` (new file)

```python
import pytest
from backend.connectors.mock_connector import MockConnector
from backend.connectors.base import RateFetchError

@pytest.mark.asyncio
async def test_get_historical_rates_returns_correct_date_range():
    """Series has exactly (end - start + 1) entries."""

@pytest.mark.asyncio
async def test_get_historical_rates_deterministic():
    """Same call twice returns identical rates."""

@pytest.mark.asyncio
async def test_get_historical_rates_error_pair_raises():
    """error_pairs injection raises RateFetchError on first call."""

@pytest.mark.asyncio
async def test_get_historical_rates_single_day():
    """start_date == end_date returns exactly one entry."""

@pytest.mark.asyncio
async def test_get_historical_rates_multiple_targets():
    """Each date entry contains all requested target currencies."""
```

### 3.2 `backend/tests/unit/test_cache.py` (new file)

```python
import pytest, time
from backend.cache import RateCache

def test_cache_miss_returns_none():
    """Empty cache returns None for any key."""

def test_cache_hit_returns_value():
    """set then get returns same object."""

def test_cache_ttl_expiry(monkeypatch):
    """Entry expired after TTL; monkeypatch time.monotonic."""

def test_cache_lru_eviction():
    """max_entries=2: third insert evicts oldest."""

def test_cache_key_normalises_target_order():
    """[EUR, GBP] and [GBP, EUR] hit the same cache key."""
```

### 3.3 `backend/tests/unit/test_schemas.py` — additions to existing file

```python
def test_historical_rates_request_uppercases_fields():
    """base and targets are uppercased by validator."""

def test_historical_rates_request_rejects_bad_date_format():
    """Non-ISO date string raises ValidationError."""

def test_dashboard_config_rejects_zero_panels():
    """Empty panels list raises ValidationError."""

def test_dashboard_config_rejects_too_many_panels():
    """10 panels raises ValidationError (max=9)."""
```

### 3.4 `backend/tests/e2e/test_dashboard_api.py` (new file)

```python
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.connectors.mock_connector import MockConnector

@pytest.fixture
def client():
    app = create_app()
    app.state.connector = MockConnector()
    return TestClient(app)

def test_historical_rates_endpoint_happy_path(client):
    """POST /api/rates/historical returns 200 with correct series length."""

def test_historical_rates_endpoint_cache_hit(client):
    """Second identical POST returns cached=True."""

def test_historical_rates_endpoint_422_on_bad_request(client):
    """Missing base field returns HTTP 422."""

def test_dashboard_endpoint_happy_path(client):
    """POST /api/dashboard with 2 panels returns 2 panel results."""

def test_dashboard_endpoint_502_on_connector_error(client):
    """ConnectorError from mock propagates as HTTP 502."""

def test_existing_chat_endpoint_still_works(client):
    """POST /api/chat unaffected by dashboard additions."""
```

### 3.5 `backend/tests/unit/test_tools.py` — additions to existing file

```python
@pytest.mark.asyncio
async def test_dispatch_tool_get_historical_rates():
    """dispatch_tool routes get_historical_rates to connector correctly."""

@pytest.mark.asyncio
async def test_dispatch_tool_unknown_tool_raises_agent_error():
    """Already exists — confirm still passes after new tool added."""
```

