# AI Market Studio — Data Layer Design

> Authored by: Data Engineer specialist agent
> Date: 2026-03-26
> Status: Feature 02 — Historical Rate Dashboard

---

## 1. Overview

This document specifies the complete design of the Data Connector Layer for AI Market Studio, covering both Feature 01 (spot rates) and Feature 02 (historical rate dashboard). It covers:

- Abstract base class interface (`MarketDataConnector`) — updated for date-range queries
- Canonical data schemas for spot rates and historical time-series
- `ExchangeRateHostConnector` implementation contract and endpoint mapping
- `MockConnector` extensions for deterministic time-series test data
- Caching strategy to protect the 100 req/month free-tier quota
- Error hierarchy additions
- Dashboard panel data contracts
- Data quality considerations

---

## 2. Canonical Data Schemas

### 2.1 SpotRate (Feature 01 — unchanged)

```python
@dataclass
class SpotRate:
    base: str       # ISO 4217, e.g. "USD"
    target: str     # ISO 4217, e.g. "EUR"
    rate: float     # units of target per 1 base
    timestamp: str  # ISO 8601 UTC, e.g. "2026-03-26T12:00:00Z"
    source: str     # connector identifier, e.g. "exchangerate.host"
```

Dict contract (returned by agent tools):

```json
{
  "base": "USD",
  "target": "EUR",
  "rate": 0.9234,
  "timestamp": "2026-03-26T12:00:00Z",
  "source": "exchangerate.host"
}
```

### 2.2 HistoricalRatePoint — single date observation (Feature 02)

```python
@dataclass
class HistoricalRatePoint:
    base: str    # ISO 4217
    target: str  # ISO 4217
    rate: float  # units of target per 1 base
    date: str    # ISO 8601 date: "YYYY-MM-DD"
    source: str  # connector identifier
```

Dict contract:

```json
{
  "base": "USD",
  "target": "EUR",
  "rate": 0.9234,
  "date": "2026-03-01",
  "source": "exchangerate.host"
}
```

### 2.3 HistoricalRateSeries — time series for a currency pair (Feature 02)

```python
@dataclass
class HistoricalRateSeries:
    base: str                          # ISO 4217
    target: str                        # ISO 4217
    start_date: str                    # "YYYY-MM-DD"
    end_date: str                      # "YYYY-MM-DD"
    points: list[HistoricalRatePoint]  # sorted ascending by date
    source: str                        # connector identifier
    cache_hit: bool                    # True if all points served from cache
```

**Invariants:**
- `points` is always sorted ascending by `date`.
- Gaps are allowed (weekends, holidays) — callers must not assume daily continuity.
- `len(points)` may be less than `(end_date - start_date).days + 1` due to gaps.
- EOD rates only — no intraday granularity.

Dict contract:

```json
{
  "base": "USD",
  "target": "EUR",
  "start_date": "2026-03-01",
  "end_date": "2026-03-31",
  "points": [
    {"base": "USD", "target": "EUR", "rate": 0.9234, "date": "2026-03-01", "source": "exchangerate.host"},
    {"base": "USD", "target": "EUR", "rate": 0.9210, "date": "2026-03-02", "source": "exchangerate.host"}
  ],
  "source": "exchangerate.host",
  "cache_hit": true
}
```

### 2.4 MultiPairSeries — multiple pairs over the same date range (Feature 02)

```python
@dataclass
class MultiPairSeries:
    pairs: list[tuple[str, str]]             # [(base, target), ...]
    start_date: str
    end_date: str
    series: dict[str, HistoricalRateSeries]  # key: "BASE/TARGET"
    source: str
```

Key format: `f"{base}/{target}"` — e.g. `"USD/EUR"`.

---

## 3. Abstract Base Class — MarketDataConnector

### File: `backend/connectors/base.py`

> **Alignment note:** Method signature aligned with `docs/architecture_design.md` section 5.2 (SRE/Architect spec). The primary date-range method is `get_historical_rates` returning `list[dict]` — a compact, cache-friendly contract. The richer `HistoricalRateSeries` dataclass (section 2.3) is used internally but is not the ABC return type.

```python
from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

class MarketDataConnector(ABC):
    source_name: str  # must be set by subclass

    # --- Feature 01 (unchanged) ---

    @abstractmethod
    async def get_exchange_rate(
        self, base: str, target: str, date: Optional[str] = None
    ) -> dict: ...

    @abstractmethod
    async def get_exchange_rates(
        self, base: str, targets: list[str]
    ) -> dict: ...

    @abstractmethod
    async def list_supported_currencies(self) -> dict: ...

    # --- Feature 02 (new) ---

    @abstractmethod
    async def get_historical_rates(
        self,
        base: str,
        quote: str,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """
        Return EOD rates for [start_date, end_date] inclusive.
        Return type: [{"date": "YYYY-MM-DD", "rate": float}, ...] sorted ascending.
        Raises ValueError if start_date > end_date.
        Raises DateRangeExceededError if range > MAX_HISTORICAL_DAYS.
        Raises RateNotAvailableError if data is unavailable for the range.
        Non-USD cross-rates are resolved via USD triangulation per date;
        the derived rate is returned (not the USD legs).
        """
        ...
```

### Method Summary

| Method | New? | Return type | Notes |
|---|---|---|---|
| `get_exchange_rate` | No | `dict` | Spot rate, optional date string |
| `get_exchange_rates` | No | `dict` | Multi-target spot |
| `list_supported_currencies` | No | `dict` | Currency list |
| `get_historical_rates` | Yes | `list[dict]` | Date range, compact point list |

### list[dict] Point Schema

```json
[{"date": "2026-03-01", "rate": 0.9234}, {"date": "2026-03-02", "rate": 0.9210}]
```

This is the canonical wire format used at the ABC boundary and in API responses. The `HistoricalRateSeries` dataclass (section 2.3) is an internal implementation detail of connectors that need richer metadata.

---

## 4. Error Hierarchy

### File: `backend/connectors/base.py` (additions)

```python
class ConnectorError(Exception):
    """Base exception for all connector-layer errors."""

class RateFetchError(ConnectorError):
    """HTTP error, timeout, or parse failure fetching a rate."""

class UnsupportedPairError(ConnectorError):
    """Currency pair not supported by the data source."""

class StaleDataError(ConnectorError):
    """Returned data is older than acceptable threshold."""

# Feature 02 additions:

class RateNotAvailableError(ConnectorError):
    """
    No rate data exists for the requested date.
    Typical causes: future date, weekend/holiday with no EOD data,
    date before the source's coverage start.
    """

class DateRangeExceededError(ConnectorError):
    """
    Requested date range exceeds the configured maximum.
    Raised before any API calls are made.
    Default limit: MAX_HISTORICAL_DAYS (default 31).
    """

class QuotaGuardError(ConnectorError):
    """
    Operation would exceed the estimated monthly API quota.
    Raised when USE_MOCK_CONNECTOR=false and estimated calls > quota threshold.
    """
```

### Error Mapping

| Scenario | Exception |
|---|---|
| HTTP 4xx/5xx from exchangerate.host | `RateFetchError` |
| Future date requested | `RateNotAvailableError` |
| Date range > MAX_HISTORICAL_DAYS | `DateRangeExceededError` |
| Unsupported currency code | `UnsupportedPairError` |
| Quota guard triggered | `QuotaGuardError` |

---

## 5. exchangerate.host Endpoint Mapping

### 5.1 Endpoint Reference

| Connector Method | Endpoint | Notes |
|---|---|---|
| `get_exchange_rate` | `GET /live` | Existing Feature 01 |
| `get_exchange_rates` | `GET /live` with multi `symbols` | Existing Feature 01 |
| `list_supported_currencies` | `GET /list` | Existing Feature 01 |
| `get_historical_rates` | `GET /timeseries` (preferred) | 1 call per pair, full range |
| `get_historical_rates` | `GET /historical` loop (fallback) | N calls for N days |

### 5.2 /timeseries Endpoint — NOT AVAILABLE ON FREE TIER

> **CONFIRMED (2026-03-26):** `/timeseries` requires the Basic paid plan ($14.99/month, 10k req/month). It is not available on the free tier. The free tier supports `/live` and `/historical` (single date per call) only.
>
> Future upgrade path: if the team moves to a paid plan, replace the `/historical` loop in `get_historical_rates` with a single `/timeseries` call per pair. Response shape: `{"rates": {"YYYY-MM-DD": {"EUR": 0.9234}, ...}}` — each date written to cache individually after the call.

### 5.3 /historical Loop (Only Option on Free Tier)

```
GET https://api.exchangerate.host/historical
    ?access_key={EXCHANGERATE_API_KEY}
    &date=2026-03-01
    &base=USD
    &symbols=EUR,GBP
```

- `symbols` accepts comma-separated targets — batch multiple targets for the same base+date into a single call (reduces calls when multiple quotes share a base).
- N-day range = N sequential calls per pair. Cache checks before each call to skip already-cached dates.

### 5.4 Non-USD Triangulation (both endpoints)

For non-USD base pairs (e.g. EUR/GBP): fetch `USD/EUR` and `USD/GBP`, compute:
```
rate(EUR→GBP) = rate(USD→GBP) / rate(USD→EUR)
```
Applied **per date** in the series. The **derived cross-rate is stored in cache** — not the intermediate USD legs. Cache key: `("EUR", "GBP", "2026-03-01")`.

### 5.3 Response Parsing — Historical

```json
{
  "success": true,
  "historical": true,
  "date": "2026-03-01",
  "base": "USD",
  "rates": {
    "EUR": 0.9234,
    "GBP": 0.7891
  }
}
```

Map `rates[target]` → `HistoricalRatePoint.rate`. If `success` is false, raise `RateFetchError`.

---

## 6. Quota Impact Analysis

### 6.1 Free Tier Budget

- **Limit:** ~100 requests/month
- **`/timeseries` endpoint:** NOT available on free tier (requires Basic plan, $14.99/month)
- **Only available endpoints:** `/live` (spot) and `/historical` (single date per call)
- **Feature 01 spot calls:** 1-2 calls per chat query
- **Feature 02 historical series:** N calls per pair (1 call per calendar day in range)

### 6.2 Call Volume Estimates (no cache, free tier — sequential /historical calls)

| Dashboard Type | Date Range | Pairs | API Calls (cold cache) |
|---|---|---|---|
| 7-day trend, 1 pair | 7 days | 1 | 7 |
| 30-day trend, 1 pair | 30 days | 1 | 30 |
| 30-day trend, 3 pairs | 30 days | 3 | **90 — exhausts monthly quota** |
| 90-day trend, 1 pair | 90 days | 1 | 90 — exhausts monthly quota |

**A single 30-day, 3-pair dashboard exhausts the entire monthly free-tier quota on cold cache.**

With warm cache (all dates cached from a prior load): 0 additional API calls.

### 6.3 Guardrails

| Guardrail | Recommended Default | Config Env Var | Notes |
|---|---|---|---|
| Max date range per call | **7 days** (free tier) | `MAX_HISTORICAL_DAYS` | 31 days safe only with warm cache; 7 days = safe cold-cache budget for 1-2 pairs |
| Max pairs per multi-pair call | 5 | `MAX_DASHBOARD_PAIRS` | — |
| Today's date | Not cached | — | Volatile until market close |

Raise `DateRangeExceededError` before any API call if range exceeds `MAX_HISTORICAL_DAYS`.

> **Recommendation:** Default `MAX_HISTORICAL_DAYS=7` for free-tier PoC. Document that 30-day dashboards require either a paid plan or a warm cache. Upgrade to Basic plan ($14.99/month) to unlock `/timeseries` (1 call/pair regardless of range) and raise practical limit to 365 days.

---

## 7. Caching Strategy

### 7.1 Architecture

- **Type:** In-memory dict, process-local, no external dependency (Redis out of scope for PoC)
- **Key:** `(base, target, date_str)` tuple — e.g. `("USD", "EUR", "2026-03-01")`
- **Value:** `HistoricalRatePoint` + `fetched_at` timestamp
- **TTL:** 24 hours for past dates; today's date is never cached (rates are live)
- **Scope:** Per-connector instance (injected as singleton via FastAPI dependency)

### 7.2 RateCache Implementation

### File: `backend/connectors/cache.py`

> **Alignment note:** Schema aligned with `docs/architecture_design.md` section 8.3. Module-level dict with `asyncio.Lock` for write safety in async context.

```python
import asyncio
import time
from datetime import date as date_type

# Key: (base, quote, date_str)  →  Value: (rate: float, stored_at_epoch: float)
_cache: dict[tuple[str, str, str], tuple[float, float]] = {}
_lock = asyncio.Lock()

TTL_SECONDS = 24 * 3600
MAX_SIZE = 3650  # ~10 years × 365 days × 1 pair


def _is_valid(stored_at_epoch: float) -> bool:
    return (time.time() - stored_at_epoch) < TTL_SECONDS


def cache_get(base: str, quote: str, date_str: str) -> float | None:
    """Return cached rate or None. Lazy TTL check on read."""
    entry = _cache.get((base, quote, date_str))
    if entry and _is_valid(entry[1]):
        return entry[0]
    return None


async def cache_set(base: str, quote: str, date_str: str, rate: float) -> None:
    """Store rate. asyncio.Lock guards writes. Never cache today's date."""
    if date_str == date_type.today().isoformat():
        return  # today's rate is volatile; never cache
    async with _lock:
        _cache[(base, quote, date_str)] = (rate, time.time())


def cache_size() -> int:
    return len(_cache)


def cache_clear() -> None:
    """For tests only."""
    _cache.clear()
```

**Key rules:**
- Key = `(base, quote, date_str)` — always the derived cross-rate, never the USD legs
- Today's date is never cached (volatile until market close)
- `asyncio.Lock` guards writes; reads are lock-free (single event loop)
- Max size ~3,650 entries at PoC scale; no active eviction needed

### 7.3 Cache Integration in ExchangeRateHostConnector

```python
async def get_historical_rates(
    self, base: str, quote: str, start_date: date, end_date: date
) -> list[dict]:
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")
    n_days = (end_date - start_date).days + 1
    max_days = int(os.getenv("MAX_HISTORICAL_DAYS", "31"))
    if n_days > max_days:
        raise DateRangeExceededError(
            f"Range {n_days} days exceeds MAX_HISTORICAL_DAYS={max_days}"
        )
    result = []
    uncached_dates = []
    current = start_date
    while current <= end_date:
        date_str = current.isoformat()
        rate = cache_get(base, quote, date_str)
        if rate is not None:
            result.append({"date": date_str, "rate": rate})
        else:
            uncached_dates.append(current)
        current += timedelta(days=1)

    if uncached_dates:
        # Attempt /timeseries for the uncached span (verify free tier availability)
        # Fallback: loop over /historical for each uncached date
        fetched = await self._fetch_range(base, quote, uncached_dates)
        for item in fetched:
            await cache_set(base, quote, item["date"], item["rate"])
            result.append(item)

    return sorted(result, key=lambda x: x["date"])
```

---

## 8. MockConnector Extensions

### 8.1 Deterministic Time-Series Generation

The mock produces stable, repeatable data with no network calls — safe for CI.

```python
import math
from datetime import date, timedelta

class MockConnector(MarketDataConnector):
    source_name = "mock"

    BASE_RATES = {
        ("USD", "EUR"): 0.9200,
        ("USD", "GBP"): 0.7850,
        ("USD", "JPY"): 149.50,
        ("USD", "AUD"): 1.5300,
        ("USD", "CAD"): 1.3600,
        ("USD", "CHF"): 0.8900,
        ("USD", "CNY"): 7.2400,
        ("USD", "HKD"): 7.8200,
        ("USD", "SGD"): 1.3400,
        ("USD", "NZD"): 1.6300,
    }

    def __init__(
        self,
        error_pairs: dict[tuple, Exception] | None = None,
        error_dates: dict[tuple, Exception] | None = None,
    ):
        """
        error_pairs: {(base, target): exception} — raises on any call for that pair
        error_dates: {(base, target, date_str): exception} — raises on a specific date
        """
        self._error_pairs = error_pairs or {}
        self._error_dates = error_dates or {}

    def _mock_rate_on_date(self, base: str, target: str, on_date: date) -> float:
        """
        Deterministic synthetic rate: sinusoidal ±2% variation over a 90-day cycle.
        Stable across runs — no randomness.
        """
        key = (base, target)
        reverse_key = (target, base)
        if key in self.BASE_RATES:
            base_rate = self.BASE_RATES[key]
        elif reverse_key in self.BASE_RATES:
            base_rate = 1.0 / self.BASE_RATES[reverse_key]
        else:
            raise UnsupportedPairError(f"Mock does not support {base}/{target}")
        day_of_year = on_date.timetuple().tm_yday
        variation = 0.02 * math.sin(2 * math.pi * day_of_year / 90)
        return round(base_rate * (1 + variation), 6)

    async def get_historical_rates(
        self, base: str, quote: str,
        start_date: date, end_date: date,
    ) -> list[dict]:
        if (base, quote) in self._error_pairs:
            raise self._error_pairs[(base, quote)]
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")
        result = []
        current = start_date
        while current <= end_date:
            date_str = current.isoformat()
            if (base, quote, date_str) in self._error_dates:
                raise self._error_dates[(base, quote, date_str)]
            rate = self._mock_rate_on_date(base, quote, current)
            result.append({"date": date_str, "rate": rate})
            current += timedelta(days=1)
        return result
```

### 8.2 MockConnector Test Patterns

```python
# Inject error for a specific pair
mock = MockConnector(error_pairs={("USD", "XYZ"): UnsupportedPairError("XYZ not supported")})

# Inject error for a specific date
mock = MockConnector(error_dates={("USD", "EUR", "2026-03-15"): RateNotAvailableError("holiday")})

# Verify determinism — same date always yields same rate
from datetime import date
mock = MockConnector()
result_a = await mock.get_historical_rates("USD", "EUR", date(2026, 3, 1), date(2026, 3, 1))
result_b = await mock.get_historical_rates("USD", "EUR", date(2026, 3, 1), date(2026, 3, 1))
assert result_a[0]["rate"] == result_b[0]["rate"]  # always true

# Simulate 503 on full pair
mock = MockConnector(error_pairs={("USD", "EUR"): RateFetchError("503 upstream")})

# Simulate partial data (error on one date mid-series)
mock = MockConnector(error_dates={("USD", "EUR", "2026-03-15"): RateNotAvailableError("holiday")})
```

---

## 9. Dashboard Panel Data Contracts

### 9.1 Panel Types

| Panel Type | Data Required | Connector Method |
|---|---|---|
| Line chart — single pair | `list[dict]` points | `get_historical_rates` |
| Multi-line chart — multiple pairs | N × `list[dict]` | `get_historical_rates` per pair |
| Summary table — latest rates | spot dict | `get_exchange_rates` |
| Sparkline — 7-day trend | `list[dict]` (7 points) | `get_historical_rates` |

### 9.2 API Response Schema — POST /api/dashboard

Request:

```json
{
  "dashboard_type": "line_chart",
  "pairs": [["USD", "EUR"], ["USD", "GBP"]],
  "start_date": "2026-03-01",
  "end_date": "2026-03-31"
}
```

Response:

```json
{
  "dashboard_type": "line_chart",
  "panels": [
    {
      "pair": "USD/EUR",
      "series": {
        "base": "USD",
        "target": "EUR",
        "start_date": "2026-03-01",
        "end_date": "2026-03-31",
        "points": [
          {"date": "2026-03-01", "rate": 0.9234},
          {"date": "2026-03-02", "rate": 0.9210}
        ],
        "source": "exchangerate.host",
        "cache_hit": true
      }
    }
  ],
  "meta": {
    "generated_at": "2026-03-26T12:00:00Z",
    "total_api_calls": 0,
    "cache_hits": 31
  }
}
```

### 9.3 Chart Panel Shape (for frontend rendering)

For trend/comparison chart panels, the API serializes connector `list[dict]` data into this shape:

```json
{
  "labels": ["2026-03-01", "2026-03-02", "2026-03-03"],
  "series": [
    {"pair": "USD/EUR", "values": [0.9234, 0.9210, 0.9198]},
    {"pair": "USD/GBP", "values": [0.7850, 0.7841, 0.7863]}
  ]
}
```

- `labels`: sorted ascending date strings, union of all dates across all pairs in the panel
- `series[].values`: rate for the corresponding label date; `null` for gaps (weekends/holidays)
- Derived at the API layer from raw `list[dict]` connector output — not a connector concern

### 9.4 Stats Panel Shape (for metrics panels)

For summary/stats panels, the API computes and returns:

```json
{
  "pair": "USD/EUR",
  "metrics": {
    "min": 0.9101,
    "max": 0.9312,
    "avg": 0.9205,
    "pct_change": -0.39
  }
}
```

- `pct_change`: percentage change from first to last point in the series: `((last - first) / first) * 100`, rounded to 2 dp
- All metrics derived from the connector's `list[dict]` output at the API layer
- Connector returns raw rate points only; stats computation is a backend API responsibility, not a connector responsibility

---

## 10. Feature 01 — Existing Design (preserved)

### 10.1 get_exchange_rate / get_exchange_rates

See Feature 01 implementation in `backend/connectors/exchangerate_host.py`.

Return dict contract (unchanged):

```json
{
  "base": "USD",
  "target": "EUR",
  "rate": 0.9234,
  "timestamp": "2026-03-26T12:00:00Z",
  "source": "exchangerate.host"
}
```

### 10.2 list_supported_currencies

```json
{
  "currencies": ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "CNY", "HKD", "SGD", "NZD"],
  "source": "exchangerate.host"
}
```

### 10.3 USD Triangulation (unchanged)

Non-USD cross-rates computed as:
```
rate(A→B) = rate(A→USD) * rate(USD→B)
         = (1 / rate(USD→A)) * rate(USD→B)
```

This applies to both spot (`get_exchange_rate`) and historical (`get_historical_rates`) — same logic, applied per date. The derived cross-rate is stored in cache under `(base, quote, date_str)` — not the intermediate USD legs.

---

## 11. Data Quality Considerations

| Concern | Handling |
|---|---|
| EOD-only granularity | Documented in user guide; no intraday data available on free tier |
| Weekend/holiday gaps | Points list may have gaps; callers must not assume daily continuity |
| Future dates | `RateNotAvailableError` raised; not cached |
| Today's rate volatility | Today's date not cached; always fetches live |
| Source coverage start | exchangerate.host historical data from ~2010; no guardrail in PoC |
| Triangulation precision | Rounded to 6 decimal places; acceptable for PoC display |

---

## 12. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| ABC method name | `get_historical_rates(base, quote, start, end) -> list[dict]` | Aligned with architecture_design.md §5.2; compact wire type |
| Historical endpoint | `/historical` loop only (N calls/pair) | `/timeseries` confirmed unavailable on free tier; paid Basic plan required |
| Upgrade path | `/timeseries` on Basic plan ($14.99/mo) | 1 call/pair regardless of range; replace loop in `get_historical_rates` |
| Cache file | `backend/connectors/cache.py` module-level dict | Aligned with architecture_design.md §8.3; no external dependency |
| Cache key | `(base, quote, date_str)` → `(rate, stored_epoch)` | Derived cross-rate stored, not USD legs |
| Cache TTL | 24h, lazy eviction on read | EOD rates stable once published; simple for PoC |
| Today's date | Never cached | Volatile until market close |
| Cache writes | `asyncio.Lock` | Async-safe in FastAPI single event loop |
| Max range guardrail | **7 days default** (`MAX_HISTORICAL_DAYS` env var) | 31-day default too risky on free tier; 7 days = safe cold-cache budget |
| Mock variation | Sinusoidal ±2% by day-of-year | Deterministic, visually realistic, no randomness |
| Error injection API | `error_pairs` + `error_dates` dicts | Fine-grained test control without subclassing |
| Cross-rates | USD triangulation per date, derived rate cached | Consistent with Feature 01; transparent to callers |
| Connector interface | Abstract base class | MockConnector swap without changing agent or API code |

---

## 13. Cross-Cutting Concerns

### For Business Analyst
- **Quota impact is critical:** A single 30-day, 3-pair dashboard = 90 API calls — exhausting the free monthly quota. Dashboard use cases must default to `USE_MOCK_CONNECTOR=true` during development. Production use requires a paid exchangerate.host plan.
- **EOD only:** No intraday data. All historical rates are end-of-day closing rates.
- **Max range:** Default 31-day limit per dashboard request. Configurable via `MAX_HISTORICAL_DAYS`.

### For SRE / Architect
- **Quota exhaustion risk:** Date-range queries multiply API call volume by N days × M pairs. The in-memory cache is the primary mitigation. For production, consider a persistent cache (Redis) and a quota counter with circuit breaker.
- **No retry logic in cache-miss path:** PoC connector does not retry on transient HTTP errors. SRE should add exponential backoff for production.
- **`USE_MOCK_CONNECTOR=true` is mandatory for CI/CD** — all automated test pipelines must set this env var to avoid live API calls.
- **`MAX_HISTORICAL_DAYS` env var** must be documented in `.env.example`.

---

*End of data design document.*




