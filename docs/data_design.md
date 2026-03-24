# AI Market Studio — Data Layer Design

> Authored by: Data Engineer specialist agent
> Date: 2026-03-25
> Status: Final (PoC)

---

## 1. Overview

This document specifies the complete design of the Data Connector Layer for the AI Market Studio PoC. It covers:

- Abstract base class interface (`MarketDataConnector`)
- FX data schema (canonical dict contract)
- `ExchangeRateHostConnector` implementation contract
- `MockConnector` for testing
- Error handling strategy
- Connector registration / discovery pattern
- exchangerate.host API reference
- Data quality considerations

---

## 2. Abstract Base Class — `MarketDataConnector`

### File: `backend/connectors/base.py`

```python
"""Abstract base class for all market data connectors.

All concrete implementations must be async-compatible and return
data normalised to the canonical FX schema defined in this module.
"""

from abc import ABC, abstractmethod
from typing import Optional


class ConnectorError(Exception):
    """Base exception for all connector-layer errors."""


class RateFetchError(ConnectorError):
    """Raised when a rate cannot be fetched (HTTP error, timeout, parse failure)."""


class UnsupportedPairError(ConnectorError):
    """Raised when the requested currency pair is not supported by the source."""


class StaleDataError(ConnectorError):
    """Raised when the returned data is older than the acceptable threshold."""


class MarketDataConnector(ABC):
    """Abstract interface for FX market data sources.

    Implementations must be async. All methods return data normalised
    to the canonical FX rate dict (see FX_RATE_SCHEMA below).
    Callers (agent layer) must only depend on this interface, never
    on a concrete implementation.
    """

    @abstractmethod
    async def get_exchange_rate(
        self,
        base: str,
        target: str,
        date: Optional[str] = None,
    ) -> dict:
        """Fetch the exchange rate for a currency pair.

        Args:
            base:   ISO 4217 base currency code, e.g. "EUR".
            target: ISO 4217 target currency code, e.g. "USD".
            date:   ISO 8601 date string ("YYYY-MM-DD") for historical
                    queries. None means latest available rate.

        Returns:
            Canonical FX rate dict (see Section 3).

        Raises:
            UnsupportedPairError: The pair is not available from this source.
            RateFetchError:       HTTP error, timeout, or unparseable response.
            StaleDataError:       Returned data exceeds staleness threshold.
        """
        ...

    @abstractmethod
    async def list_supported_currencies(self) -> list[str]:
        """Return a list of supported ISO 4217 currency codes.

        Returns:
            Sorted list of uppercase currency code strings, e.g.
            ["AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "USD", ...].

        Raises:
            RateFetchError: Could not retrieve the currency list.
        """
        ...
```

### Design Rationale

| Decision | Reason |
|---|---|
| `async` methods only | FastAPI runs an async event loop; blocking HTTP calls would stall it |
| `date: Optional[str]` | Keeps agent tool signature simple; None = latest |
| ISO 8601 string for date | Avoids `datetime` serialisation complexity at the boundary |
| Exceptions in base module | Agent layer imports one module for error types — no coupling to concrete classes |
| `list[str]` not `List[str]` | Python 3.11+ built-in generics |

---

## 3. Canonical FX Rate Schema

Every `get_exchange_rate()` call returns a plain `dict` matching this schema. This is the contract between the connector layer and the agent layer.

```python
FX_RATE_SCHEMA = {
    "base":      str,   # ISO 4217 base currency, e.g. "EUR" (uppercased)
    "target":    str,   # ISO 4217 target currency, e.g. "USD" (uppercased)
    "rate":      float, # Exchange rate: 1 base unit = rate target units
    "timestamp": str,   # ISO 8601 datetime string of rate validity, e.g. "2026-03-25T00:00:00Z"
    "date":      str,   # ISO 8601 date string, e.g. "2026-03-25"
    "source":    str,   # Data source identifier, e.g. "exchangerate.host"
    "is_mock":   bool,  # True only for MockConnector responses
}
```

### Example Instance

```json
{
  "base": "EUR",
  "target": "USD",
  "rate": 1.0823,
  "timestamp": "2026-03-25T00:05:00Z",
  "date": "2026-03-25",
  "source": "exchangerate.host",
  "is_mock": false
}
```

### Field Notes

| Field | Required | Notes |
|---|---|---|
| `base` | Yes | Always uppercased before return |
| `target` | Yes | Always uppercased before return |
| `rate` | Yes | Always a positive float; never zero or negative |
| `timestamp` | Yes | UTC. If source provides Unix epoch, convert to ISO 8601 |
| `date` | Yes | Derived from `timestamp` if not separately provided |
| `source` | Yes | Hard-coded per connector; enables provenance tracking |
| `is_mock` | Yes | Allows agent layer to tag responses for transparency |

---

## 4. exchangerate.host API Reference

### 4.1 API Key Requirement

> **IMPORTANT — Breaking change from team_context.md assumption:**
> exchangerate.host was acquired by APILayer and **now requires an API key** (`access_key` query parameter) even on the free tier (100 req/month).
> The `EXCHANGERATE_HOST_API_KEY` environment variable must be added to `.env.example` and `config.py`.
> Free tier restricts the source/base currency to **USD only**.

### 4.2 Base URL

```
https://api.exchangerate.host
```

Configurable via `EXCHANGERATE_HOST_BASE_URL` env var (for test overriding with `respx`).

### 4.3 Endpoints Used by This PoC

#### GET `/live` — Latest Rates

```
GET https://api.exchangerate.host/live
    ?access_key={key}
    &source={base}         # e.g. USD
    &currencies={target}   # e.g. EUR,GBP (comma-separated)
    &format=1
```

**Response:**
```json
{
  "success": true,
  "source": "USD",
  "timestamp": 1742860800,
  "quotes": {
    "USDEUR": 0.9234,
    "USDGBP": 0.7891
  }
}
```

**Notes:**
- `quotes` keys are always `{source}{target}` concatenated (6 chars, no separator).
- `timestamp` is Unix epoch (seconds).
- On free tier, `source` must be `USD`.

#### GET `/historical` — Historical Rate

```
GET https://api.exchangerate.host/historical
    ?access_key={key}
    &date={YYYY-MM-DD}
    &source={base}
    &currencies={target}
    &format=1
```

**Response:** Same structure as `/live` but reflects end-of-day rate for the given date.

#### GET `/list` — Supported Currencies

```
GET https://api.exchangerate.host/list
    ?access_key={key}
    &format=1
```

**Response:**
```json
{
  "success": true,
  "currencies": {
    "AUD": "Australian Dollar",
    "EUR": "Euro",
    "USD": "United States Dollar"
  }
}
```

### 4.4 Rate Limits (Free Tier)

| Limit | Value |
|---|---|
| Monthly requests | 100 |
| Base currency restriction | USD only |
| Notifications at | 75%, 90%, 100% of quota |
| HTTPS required | Yes |

### 4.5 Error Responses

When `success` is `false`, the response includes an `error` object:

```json
{
  "success": false,
  "error": {
    "code": 101,
    "type": "invalid_access_key",
    "info": "You have not supplied a valid API Access Key."
  }
}
```

| Error Code | Meaning |
|---|---|
| 101 | Invalid or missing access key |
| 104 | Monthly quota exceeded |
| 105 | Endpoint not available on current plan |
| 106 | No results for query |
| 201 | Invalid source currency |
| 202 | Invalid target currency |

---

## 5. `ExchangeRateHostConnector` Implementation Contract

### File: `backend/connectors/exchangerate_host.py`

```python
"""Concrete adapter for exchangerate.host REST API."""

import httpx
from datetime import datetime, timezone
from typing import Optional

from .base import (
    MarketDataConnector,
    RateFetchError,
    UnsupportedPairError,
)

SOURCE_ID = "exchangerate.host"
_QUOTE_KEY_LEN = 6  # e.g. "USDEUR"


class ExchangeRateHostConnector(MarketDataConnector):
    """Adapter for exchangerate.host API.

    Args:
        api_key:  exchangerate.host access_key.
        base_url: API base URL (override in tests via respx).
        timeout:  HTTP request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.exchangerate.host",
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def get_exchange_rate(
        self,
        base: str,
        target: str,
        date: Optional[str] = None,
    ) -> dict:
        base = base.upper()
        target = target.upper()
        endpoint = "/historical" if date else "/live"

        # Preferred: single call with arbitrary source (GAP-02).
        # The API accepts source={base} for any currency directly.
        params: dict = {
            "access_key": self._api_key,
            "source": base,
            "currencies": target,
            "format": 1,
        }
        if date:
            params["date"] = date

        try:
            raw = await self._get(endpoint, params)
            return self._parse_rate(raw, base, target)
        except UnsupportedPairError:
            # Fallback: source not supported — fetch both legs from USD in one call,
            # compute cross rate in-process. Single HTTP call, no extra latency.
            if base == "USD":
                raise  # USD itself unsupported — nothing to fall back to
            usd_params: dict = {
                "access_key": self._api_key,
                "source": "USD",
                "currencies": f"{base},{target}",
                "format": 1,
            }
            if date:
                usd_params["date"] = date
            raw = await self._get(endpoint, usd_params)
            quotes = raw.get("quotes", {})
            usd_base = quotes.get(f"USD{base}")
            usd_target = quotes.get(f"USD{target}")
            if not usd_base or not usd_target:
                raise UnsupportedPairError(
                    f"Cannot derive {base}/{target} via USD pivot: "
                    f"missing legs in {list(quotes.keys())}"
                )
            cross = usd_target / usd_base
            raw["quotes"] = {f"{base}{target}": cross}
            raw["source"] = base
            return self._parse_rate(raw, base, target)

    async def list_supported_currencies(self) -> list[str]:
        raw = await self._get("/list", {"access_key": self._api_key, "format": 1})
        try:
            return sorted(raw["currencies"].keys())
        except (KeyError, AttributeError) as exc:
            raise RateFetchError(f"Unexpected /list response: {raw}") from exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get(self, endpoint: str, params: dict) -> dict:
        """Perform a GET request and return parsed JSON. Raises RateFetchError on any failure."""
        url = f"{self._base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise RateFetchError(f"Timeout calling {url}") from exc
        except httpx.HTTPStatusError as exc:
            raise RateFetchError(
                f"HTTP {exc.response.status_code} from {url}"
            ) from exc
        except Exception as exc:
            raise RateFetchError(f"Unexpected error calling {url}: {exc}") from exc

        if not data.get("success"):
            err = data.get("error", {})
            code = err.get("code", 0)
            if code in (201, 202, 106):
                raise UnsupportedPairError(
                    f"Unsupported pair or no results: {err.get('info', data)}"
                )
            raise RateFetchError(f"API error {code}: {err.get('info', data)}")

        return data

    def _parse_rate(self, data: dict, base: str, target: str) -> dict:
        """Extract and normalise the rate from a /live or /historical response."""
        quote_key = f"{base}{target}"
        quotes = data.get("quotes", {})
        rate = quotes.get(quote_key)
        if rate is None:
            raise UnsupportedPairError(
                f"Quote key '{quote_key}' not found in response. "
                f"Available keys: {list(quotes.keys())}"
            )
        ts_epoch = data.get("timestamp")
        if ts_epoch:
            dt = datetime.fromtimestamp(ts_epoch, tz=timezone.utc)
            timestamp = dt.isoformat().replace("+00:00", "Z")
            date_str = dt.strftime("%Y-%m-%d")
        else:
            timestamp = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
            date_str = timestamp[:10]
        return {
            "base": base,
            "target": target,
            "rate": float(rate),
            "timestamp": timestamp,
            "date": date_str,
            "source": SOURCE_ID,
            "is_mock": False,
        }
```

---

## 6. `MockConnector` Implementation Contract

### File: `backend/connectors/mock.py`

```python
"""Mock connector for unit and agent tests. No HTTP calls made."""

from datetime import datetime, timezone
from typing import Optional

from .base import MarketDataConnector, RateFetchError, UnsupportedPairError

_MOCK_RATES: dict[str, float] = {
    "EURUSD": 1.0823,
    "USDEUR": 0.9239,
    "GBPUSD": 1.2654,
    "USDGBP": 0.7902,
    "USDJPY": 151.42,
    "JPYUSD": 0.006605,
    "EURGBP": 0.8554,
    "GBPEUR": 1.1690,
    "USDCHF": 0.9012,
    "CHFUSD": 1.1096,
    "AUDUSD": 0.6523,
    "USDCAD": 1.3581,
}

_MOCK_TIMESTAMP = "2026-03-25T00:05:00Z"
_MOCK_DATE = "2026-03-25"
SOURCE_ID = "mock"


class MockConnector(MarketDataConnector):
    """In-memory connector returning hard-coded rates. No I/O.

    Supports optional rate injection and error injection via constructor
    for parameterised tests.

    Args:
        rates:        Override the default mock rate table. Keys are
                      concatenated pair strings e.g. "EURUSD".
        fail_pairs:   Set of pair strings (e.g. {"EURUSD"}) that raise
                      UnsupportedPairError. Pair-level granularity.
        error_pairs:  Set of currency codes (e.g. {"EUR"}) where any
                      request involving that currency as base OR target
                      raises RateFetchError. Simulates upstream API
                      failure for TC-CONN-08 / TC-E2E-04 style tests.
    """

    def __init__(
        self,
        rates: dict[str, float] | None = None,
        fail_pairs: set[str] | None = None,
        error_pairs: set[str] | None = None,
    ) -> None:
        self._rates = rates if rates is not None else dict(_MOCK_RATES)
        self._fail_pairs = fail_pairs or set()
        self._error_pairs = {c.upper() for c in (error_pairs or set())}

    async def get_exchange_rate(
        self,
        base: str,
        target: str,
        date: str | None = None,
    ) -> dict:
        base_u = base.upper()
        target_u = target.upper()
        key = f"{base_u}{target_u}"
        # Currency-level error injection — simulates connector/API failure
        if base_u in self._error_pairs or target_u in self._error_pairs:
            raise RateFetchError(
                f"Mock: currency {base_u if base_u in self._error_pairs else target_u} "
                f"flagged for error injection"
            )
        # Pair-level unsupported injection
        if key in self._fail_pairs:
            raise UnsupportedPairError(f"Mock: pair {key} marked as unsupported")
        rate = self._rates.get(key)
        if rate is None:
            raise UnsupportedPairError(f"Mock: no rate for pair {key}")
        return {
            "base": base_u,
            "target": target_u,
            "rate": rate,
            "timestamp": _MOCK_TIMESTAMP,
            "date": date or _MOCK_DATE,
            "source": SOURCE_ID,
            "is_mock": True,
        }

    async def list_supported_currencies(self) -> list[str]:
        codes: set[str] = set()
        for key in self._rates:
            codes.add(key[:3])
            codes.add(key[3:])
        return sorted(codes)
```

### MockConnector Usage Patterns

```python
# Basic usage — default rates
connector = MockConnector()
result = await connector.get_exchange_rate("EUR", "USD")
assert result["rate"] == 1.0823
assert result["is_mock"] is True

# Injecting custom rates for a specific test
connector = MockConnector(rates={"EURUSD": 1.10})

# Testing UnsupportedPairError path (pair-level)
connector = MockConnector(fail_pairs={"EURUSD"})
with pytest.raises(UnsupportedPairError):
    await connector.get_exchange_rate("EUR", "USD")

# Testing RateFetchError via currency-level error injection (TC-CONN-08 / TC-E2E-04)
# Any pair involving EUR as base OR target raises RateFetchError
connector = MockConnector(error_pairs={"EUR"})
with pytest.raises(RateFetchError):
    await connector.get_exchange_rate("EUR", "USD")  # base flagged
with pytest.raises(RateFetchError):
    await connector.get_exchange_rate("GBP", "EUR")  # target flagged

# Combining: EUR errors, GBPUSD unsupported, custom rate for USDJPY
connector = MockConnector(
    rates={"USDJPY": 148.50},
    fail_pairs={"GBPUSD"},
    error_pairs={"EUR"},
)
```

---

## 7. Error Handling Strategy

### 7.1 Exception Hierarchy

```
Exception
└── ConnectorError           (base.py — import this for broad catch)
    ├── RateFetchError        # transport / API-level failure
    ├── UnsupportedPairError  # semantic: pair does not exist
    └── StaleDataError        # temporal: data too old
```

### 7.2 How the Agent Layer Handles Connector Errors

The agent layer (`backend/agent/tools.py`) wraps every connector call in a try/except and returns a structured error dict as the tool result. GPT-4o then synthesises a user-friendly message from that.

```python
try:
    result = await connector.get_exchange_rate(base, target, date)
except UnsupportedPairError as exc:
    return {"error": "unsupported_pair", "detail": str(exc)}
except RateFetchError as exc:
    return {"error": "fetch_failed", "detail": str(exc)}
except ConnectorError as exc:
    return {"error": "connector_error", "detail": str(exc)}
```

### 7.3 Error Handling Rules

| Scenario | Exception | Agent Response |
|---|---|---|
| Invalid currency code | `UnsupportedPairError` | "I don't have data for that pair" |
| HTTP 4xx from API | `RateFetchError` | "Unable to fetch rate, try again" |
| HTTP 5xx / timeout | `RateFetchError` | "Data source unavailable" |
| API quota exceeded | `RateFetchError` (code 104) | "Rate limit reached" |
| Malformed JSON | `RateFetchError` | "Unexpected response from data source" |
| Data older than 24h | `StaleDataError` | "Rate data may be outdated" |

### 7.4 Staleness Threshold

For the PoC, staleness checking is **not enforced** in `ExchangeRateHostConnector` (exchangerate.host updates at 00:05 UTC daily — this is expected). `StaleDataError` is reserved for future connectors with real-time feeds where lag > N seconds signals a problem.

---

## 8. Connector Registration / Discovery Pattern

For the PoC, connector instantiation uses a **simple factory function** in `backend/connectors/__init__.py`. No plugin system, no dynamic import, no registry dict.

```python
# backend/connectors/__init__.py

from .base import MarketDataConnector, ConnectorError, RateFetchError, UnsupportedPairError, StaleDataError
from .exchangerate_host import ExchangeRateHostConnector
from .mock import MockConnector


def get_connector(settings) -> MarketDataConnector:
    """Factory: return the configured connector instance.

    Args:
        settings: app Settings object (from backend/config.py).

    Returns:
        A MarketDataConnector instance ready for use.
    """
    if settings.use_mock_connector:
        return MockConnector()
    return ExchangeRateHostConnector(
        api_key=settings.exchangerate_host_api_key,
        base_url=settings.exchangerate_host_base_url,
    )
```

### Required Settings Fields

```python
# backend/config.py additions
use_mock_connector: bool = False          # set True in test env
exchangerate_host_api_key: str = ""       # from EXCHANGERATE_HOST_API_KEY env var
exchangerate_host_base_url: str = "https://api.exchangerate.host"
```

### `.env.example` entries

```
EXCHANGERATE_HOST_API_KEY=your_free_tier_key_here
USE_MOCK_CONNECTOR=false
```

---

## 9. Data Quality Considerations

### 9.1 Free Tier Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| Base currency locked to USD (unverified) | `source` param may accept arbitrary base — needs live verification | Preferred: single call with `source={base}`. Fallback only if unsupported: one call with `source=USD`, compute cross rate in-process. |
| 100 req/month | Exhausted quickly in dev | Use MockConnector in all automated tests; reserve live calls for manual demos |
| EOD rates only (updated 00:05 UTC) | Rates are up to ~24h old | Document clearly in agent response ("as of YYYY-MM-DD") |

### 9.2 Cross-Rate Strategy (updated per SRE GAP-02)

**Preferred — single call with arbitrary `source`:**

The `/live` and `/historical` endpoints accept `source={base}` for any currency, not just USD. Implementation should attempt this directly:

```
GET /live?source=EUR&currencies=GBP  →  {"quotes": {"EURGBP": 0.8554}}
```

This is one HTTP call, ~200-800ms, well within the 10s SLO.

**Fallback — USD pivot (single call + in-process division):**

Only if the API rejects the requested `source` (HTTP error or `success: false`), fall back to a single USD-based call fetching both legs, then compute the cross rate in-process:

```
GET /live?source=USD&currencies=EUR,GBP
cross_rate = quotes["USDGBP"] / quotes["USDEUR"]
```

This is still one HTTP call — no sequential requests. The fallback is transparent to the caller.

> Note: Verify `source` parameter behaviour against the live API during implementation. If arbitrary base currencies are fully supported, the fallback path can be removed entirely.

### 9.3 Missing / Invalid Pairs

- Unknown ISO codes → `UnsupportedPairError` with descriptive message
- Empty `quotes` dict in response → `UnsupportedPairError`
- `rate` value of 0 or negative → log warning, raise `RateFetchError` (data integrity violation)

### 9.4 API Downtime Handling

- HTTP errors → `RateFetchError` immediately (no retry in PoC)
- Timeout set to 10s (configurable) — fail fast to avoid blocking FastAPI
- No caching in PoC — each request hits the API. Future: add Redis TTL cache.

### 9.5 Currency Code Validation

- Input currency codes are uppercased by the connector before use
- No length/format validation enforced in connector (kept simple for PoC)
- Agent tool schema restricts inputs to known codes via enum or description guidance

---

## 10. Test Design Notes

### File: `tests/unit/test_connector.py`

Use `respx` to mock the `httpx.AsyncClient` at the transport level.

```python
import pytest
import respx
from httpx import Response
from backend.connectors.exchangerate_host import ExchangeRateHostConnector
from backend.connectors.base import UnsupportedPairError, RateFetchError

BASE_URL = "https://api.exchangerate.host"

@pytest.fixture
def connector():
    return ExchangeRateHostConnector(api_key="test-key", base_url=BASE_URL)

@respx.mock
@pytest.mark.asyncio
async def test_get_exchange_rate_success(connector):
    respx.get(f"{BASE_URL}/live").mock(return_value=Response(200, json={
        "success": True,
        "source": "USD",
        "timestamp": 1742860800,
        "quotes": {"USDEUR": 0.9234},
    }))
    result = await connector.get_exchange_rate("USD", "EUR")
    assert result["base"] == "USD"
    assert result["target"] == "EUR"
    assert result["rate"] == 0.9234
    assert result["is_mock"] is False
    assert result["source"] == "exchangerate.host"

@respx.mock
@pytest.mark.asyncio
async def test_unsupported_pair_raises(connector):
    respx.get(f"{BASE_URL}/live").mock(return_value=Response(200, json={
        "success": False,
        "error": {"code": 202, "type": "invalid_currency_codes", "info": "Invalid currency."}
    }))
    with pytest.raises(UnsupportedPairError):
        await connector.get_exchange_rate("USD", "INVALID")

@respx.mock
@pytest.mark.asyncio
async def test_timeout_raises_rate_fetch_error(connector):
    import httpx
    respx.get(f"{BASE_URL}/live").mock(side_effect=httpx.TimeoutException("timed out"))
    with pytest.raises(RateFetchError, match="Timeout"):
        await connector.get_exchange_rate("USD", "EUR")
```

---

## 11. Cross-Cutting Concerns for Other Specialists

### For AI Agent Specialist
- Tool definition for `get_exchange_rate` must include `base`, `target`, `date` (optional) parameters.
- The tool dispatch must catch `ConnectorError` subclasses and return structured error dicts — not raise.
- For non-USD base pairs on free tier: agent should be aware that the connector may perform two API calls (triangulation).
- The `is_mock` field in results should be surfaced in the agent response when True ("Note: using mock data").

### For Backend / API Specialist
- `config.py` needs `exchangerate_host_api_key`, `exchangerate_host_base_url`, `use_mock_connector` fields.
- The `get_connector(settings)` factory is the single wiring point — call it once at startup and inject into the agent.
- Add `EXCHANGERATE_HOST_API_KEY` to `.env.example`.

### For SRE / Architect Specialist
- API key is a secret — must be injected via env var, never committed.
- Free tier quota (100 req/month) means the PoC will exhaust credits quickly under load testing; use `USE_MOCK_CONNECTOR=true` for all automated tests.
- No retry logic in PoC connector — SRE may want to add exponential backoff for production.
- Consider rate-limiting the `/api/chat` endpoint to protect the upstream quota.

---

## 12. Summary of Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Connector interface | Abstract base class | Enables MockConnector swap without changing agent code |
| HTTP client | `httpx.AsyncClient` | Async-native, pairs well with FastAPI; `respx` mocking support |
| Return type | Plain `dict` | Avoids Pydantic model coupling between layers in PoC; easy to serialise as tool result |
| Error types | Custom exception hierarchy | Agent layer can catch at the right level of specificity |
| Registration | Simple factory function | Zero magic, easy to read and test; sufficient for PoC |
| Free tier constraint | Triangulation for non-USD pairs | Transparent to callers; API key required (update from team_context assumption) |
| Mock data | Hard-coded rates + injectable overrides | Deterministic tests; no network dependency |
| Staleness | Not enforced in PoC | EOD-only source; `StaleDataError` reserved for real-time connectors |

---

*End of data design document.*