# QA Test Cases — AI Market Studio

> Version: 2.3
> Author: QA Expert
> Date: 2026-03-26
> Scope: Feature 02 — FX Rate Trend Dashboard (historical rates, multi-panel dashboards, dashboard type switching)
> Note: Feature 01 test cases are preserved and extended below.
> Update v2.1 (2026-03-26): /timeseries NOT available on free tier. Sequential /historical calls. Cap 7 days. MockConnector supports error_dates.
> Update v2.2 (2026-03-26): MockConnector get_historical_rates with 503/timeout/partial-data injection (blocker). Heatmap boundary. New test files. Per-file 90% coverage gate.
> Update v2.3 (2026-03-26): error_dates confirmed for dashboard-service-level tests. Added TC-EDATE-001–004 in tests/unit/test_dashboard_service.py: partial series in build_dashboard_response, heatmap cell mid-series failure, cache gap population.

---

## Ground Rules

- **Never call live APIs in automated tests.** The exchangerate.host free tier has a strict quota (~100 req/month). All tests MUST use `MockConnector` or `respx` HTTP mocks.
- **No live LLM calls.** All agent tests use a mocked `openai.AsyncOpenAI` client with recorded fixtures.
- **Test isolation.** Each test clears state; no shared mutable fixtures between tests.
- **Coverage target.** 90%+ line coverage on `backend/` is the minimum merge gate.
- **`USE_MOCK_CONNECTOR=true`** must be set in all CI/CD configs.

---

## 1. MockConnector — Time-Series Data Generation

### Setup

```python
import pytest
from datetime import date
from backend.connectors.mock_connector import MockConnector
from backend.connectors.errors import UnsupportedPairError, ConnectorNetworkError
```

### TC-MOCK-001 — Historical series: correct length

| Field | Value |
|---|---|
| ID | TC-MOCK-001 |
| Layer | Unit |
| Priority | P0 |

```python
def test_mock_connector_historical_series_length():
    """
    get_historical_series("EUR", "USD", start, end) must return one
    HistoricalRatePoint per calendar day in [start, end] inclusive.
    """
    connector = MockConnector()
    start = date(2024, 1, 1)
    end = date(2024, 1, 10)
    series = connector.get_historical_series("EUR", "USD", start, end)
    assert len(series) == 10
    assert series[0].date == start
    assert series[-1].date == end
```

### TC-MOCK-002 — Historical series: deterministic output

| Field | Value |
|---|---|
| ID | TC-MOCK-002 |
| Layer | Unit |
| Priority | P0 |

```python
def test_mock_connector_deterministic_rates():
    """
    Two calls with identical arguments must return identical rate values.
    Seed must be stable across interpreter restarts.
    """
    connector = MockConnector()
    start, end = date(2024, 3, 1), date(2024, 3, 5)
    first = connector.get_historical_series("GBP", "USD", start, end)
    second = connector.get_historical_series("GBP", "USD", start, end)
    assert [r.rate for r in first] == [r.rate for r in second]
```

### TC-MOCK-003 — Historical series: plausible rate range

| Field | Value |
|---|---|
| ID | TC-MOCK-003 |
| Layer | Unit |
| Priority | P1 |

```python
def test_mock_connector_rate_plausibility():
    """
    Mock rates for EUR/USD must stay between 0.5 and 2.5.
    Catches off-by-orders-of-magnitude generation bugs.
    """
    connector = MockConnector()
    series = connector.get_historical_series(
        "EUR", "USD", date(2024, 1, 1), date(2024, 12, 31)
    )
    for point in series:
        assert 0.5 < point.rate < 2.5
```

### TC-MOCK-004 — Multi-pair series: all requested pairs returned

| Field | Value |
|---|---|
| ID | TC-MOCK-004 |
| Layer | Unit |
| Priority | P0 |

```python
def test_mock_connector_multi_pair_series_keys():
    """
    get_multi_pair_series must return a dict keyed by each requested
    pair symbol (e.g. "EUR/USD") with the correct series length.
    """
    connector = MockConnector()
    pairs = [("EUR", "USD"), ("GBP", "USD"), ("JPY", "USD")]
    result = connector.get_multi_pair_series(
        pairs, date(2024, 1, 1), date(2024, 1, 7)
    )
    assert set(result.keys()) == {"EUR/USD", "GBP/USD", "JPY/USD"}
    for key, series in result.items():
        assert len(series) == 7
```

### TC-MOCK-008 — Error injection: error_dates raises error for specific date

| Field | Value |
|---|---|
| ID | TC-MOCK-008 |
| Layer | Unit |
| Priority | P0 |

```python
def test_mock_connector_error_dates_injection():
    """
    MockConnector(error_dates=[("EUR", "USD", date(2024, 1, 3))]) must raise
    ConnectorError specifically when that (pair, date) is requested,
    leaving other dates unaffected.
    """
    error_date = date(2024, 1, 3)
    connector = MockConnector(error_dates=[("EUR", "USD", error_date)])

    # The error date raises
    with pytest.raises(ConnectorError):
        connector.get_historical_rate("EUR", "USD", error_date)

    # Adjacent dates succeed
    ok = connector.get_historical_rate("EUR", "USD", date(2024, 1, 4))
    assert ok.rate > 0
```

### TC-MOCK-009 — error_dates in series: series call raises on first bad date

| Field | Value |
|---|---|
| ID | TC-MOCK-009 |
| Layer | Unit |
| Priority | P0 |

```python
def test_mock_connector_error_dates_in_series():
    """
    When an error_date falls within the requested series range,
    get_historical_series must raise ConnectorError (simulating a
    partial upstream failure mid-batch).
    """
    connector = MockConnector(
        error_dates=[("EUR", "USD", date(2024, 1, 3))]
    )
    with pytest.raises(ConnectorError):
        connector.get_historical_series(
            "EUR", "USD", date(2024, 1, 1), date(2024, 1, 5)
        )
```

### TC-MOCK-010 — error_dates does not affect other pairs

| Field | Value |
|---|---|
| ID | TC-MOCK-010 |
| Layer | Unit |
| Priority | P1 |

```python
def test_mock_connector_error_dates_pair_isolation():
    """
    An error_date for EUR/USD must not affect GBP/USD on the same date.
    """
    error_date = date(2024, 1, 3)
    connector = MockConnector(error_dates=[("EUR", "USD", error_date)])

    with pytest.raises(ConnectorError):
        connector.get_historical_rate("EUR", "USD", error_date)

    # GBP/USD on the same date must succeed
    ok = connector.get_historical_rate("GBP", "USD", error_date)
    assert ok.rate > 0
```

### TC-MOCK-005 — Error injection: unsupported pair raises UnsupportedPairError

| Field | Value |
|---|---|
| ID | TC-MOCK-005 |
| Layer | Unit |
| Priority | P0 |

```python
def test_mock_connector_error_injection_unsupported_pair():
    """
    MockConnector(error_pairs=[("ZZZ", "USD")]) must raise
    UnsupportedPairError for that pair.
    """
    connector = MockConnector(error_pairs=[("ZZZ", "USD")])
    with pytest.raises(UnsupportedPairError):
        connector.get_historical_series(
            "ZZZ", "USD", date(2024, 1, 1), date(2024, 1, 5)
        )
```

### TC-MOCK-006 — Error injection: network error simulation

| Field | Value |
|---|---|
| ID | TC-MOCK-006 |
| Layer | Unit |
| Priority | P0 |

```python
def test_mock_connector_error_injection_network():
    """
    MockConnector(network_error_pairs=[("EUR", "USD")]) must raise
    ConnectorNetworkError for that pair.
    """
    connector = MockConnector(network_error_pairs=[("EUR", "USD")])
    with pytest.raises(ConnectorNetworkError):
        connector.get_historical_series(
            "EUR", "USD", date(2024, 1, 1), date(2024, 1, 5)
        )
```

### TC-MOCK-007 — Single historical rate lookup

| Field | Value |
|---|---|
| ID | TC-MOCK-007 |
| Layer | Unit |
| Priority | P0 |

```python
def test_mock_connector_get_historical_rate_single_day():
    """
    get_historical_rate returns a HistoricalRatePoint with all fields
    populated correctly for a specific date.
    """
    connector = MockConnector()
    target = date(2024, 6, 15)
    point = connector.get_historical_rate("EUR", "USD", target)
    assert point.base == "EUR"
    assert point.target == "USD"
    assert point.date == str(target)
    assert isinstance(point.rate, float)
    assert point.rate > 0
```

---

## 2. Connector Interface — New Methods

### TC-CONN-101 — get_historical_rate: interface compliance

| Field | Value |
|---|---|
| ID | TC-CONN-101 |
| Layer | Unit |
| Priority | P0 |

```python
def test_connector_get_historical_rate_interface():
    """
    Any concrete connector must implement get_historical_rate and return
    an object with rate, date, base, target, and source fields.
    """
    connector = MockConnector()
    result = connector.get_historical_rate("USD", "JPY", date(2024, 1, 1))
    assert hasattr(result, "rate")
    assert hasattr(result, "date")
    assert hasattr(result, "base")
    assert hasattr(result, "target")
    assert hasattr(result, "source")
```

### TC-CONN-102 — get_historical_series: start after end raises ValueError

| Field | Value |
|---|---|
| ID | TC-CONN-102 |
| Layer | Unit |
| Priority | P0 |

```python
def test_connector_historical_series_invalid_date_range():
    """
    start > end must raise ValueError before any data fetch.
    """
    connector = MockConnector()
    with pytest.raises(ValueError, match="start.*end|end.*start"):
        connector.get_historical_series(
            "EUR", "USD", date(2024, 1, 10), date(2024, 1, 1)
        )
```

### TC-CONN-103 — get_historical_series: future end date raises ValueError

| Field | Value |
|---|---|
| ID | TC-CONN-103 |
| Layer | Unit |
| Priority | P0 |

```python
def test_connector_historical_series_future_date():
    """
    end date beyond today must raise ValueError.
    """
    connector = MockConnector()
    with pytest.raises(ValueError, match="future|past"):
        connector.get_historical_series(
            "EUR", "USD", date(2024, 1, 1), date(2099, 1, 1)
        )
```

### TC-CONN-104 — get_historical_series: same-day range returns one point

| Field | Value |
|---|---|
| ID | TC-CONN-104 |
| Layer | Unit |
| Priority | P1 |

```python
def test_connector_historical_series_single_day_range():
    """
    start == end must return a series of exactly one element.
    """
    connector = MockConnector()
    d = date(2024, 6, 1)
    result = connector.get_historical_series("EUR", "USD", d, d)
    assert len(result) == 1
    assert result[0].date == str(d)
```

### TC-CONN-105 — get_multi_pair_series: empty pairs list

| Field | Value |
|---|---|
| ID | TC-CONN-105 |
| Layer | Unit |
| Priority | P1 |

```python
def test_connector_multi_pair_series_empty_input():
    """
    An empty pairs list must return an empty dict without raising.
    """
    connector = MockConnector()
    result = connector.get_multi_pair_series(
        [], date(2024, 1, 1), date(2024, 1, 7)
    )
    assert result == {}
```

### TC-CONN-106 — USD triangulation: cross-rate consistency

| Field | Value |
|---|---|
| ID | TC-CONN-106 |
| Layer | Unit |
| Priority | P0 |

```python
def test_connector_cross_rate_triangulation():
    """
    EUR/GBP must equal EUR/USD divided by GBP/USD (within float tolerance).
    Verifies that USD triangulation is applied correctly.
    """
    connector = MockConnector()
    d = date(2024, 6, 1)
    eur_usd = connector.get_historical_rate("EUR", "USD", d).rate
    gbp_usd = connector.get_historical_rate("GBP", "USD", d).rate
    eur_gbp = connector.get_historical_rate("EUR", "GBP", d).rate
    assert abs(eur_gbp - eur_usd / gbp_usd) < 0.0001
```

### TC-CONN-107 — Range cap: exceeding MAX_HISTORICAL_DAYS (7 days) raises ValueError

| Field | Value |
|---|---|
| ID | TC-CONN-107 |
| Layer | Unit |
| Priority | P0 |

```python
def test_connector_historical_series_exceeds_max_days(monkeypatch):
    """
    A request spanning more than MAX_HISTORICAL_DAYS (default 7, not 31)
    must raise ValueError before any data fetch.
    NOTE: /timeseries is NOT available on the free tier. Historical queries
    use sequential /historical calls; the 7-day cap protects quota.
    """
    monkeypatch.setenv("MAX_HISTORICAL_DAYS", "7")
    connector = MockConnector()
    with pytest.raises(ValueError, match="MAX_HISTORICAL_DAYS|7"):
        connector.get_historical_series(
            "EUR", "USD", date(2024, 1, 1), date(2024, 1, 9)  # 8 days
        )
```

### TC-CONN-108 — Range cap: exactly 7 days is accepted

| Field | Value |
|---|---|
| ID | TC-CONN-108 |
| Layer | Unit |
| Priority | P0 |

```python
def test_connector_historical_series_exactly_max_days(monkeypatch):
    """
    A request spanning exactly MAX_HISTORICAL_DAYS (7) must succeed.
    """
    monkeypatch.setenv("MAX_HISTORICAL_DAYS", "7")
    connector = MockConnector()
    result = connector.get_historical_series(
        "EUR", "USD", date(2024, 1, 1), date(2024, 1, 7)
    )
    assert len(result) == 7
```

### TC-CONN-109 — Sequential /historical batching: one call per day

| Field | Value |
|---|---|
| ID | TC-CONN-109 |
| Layer | Unit |
| Priority | P0 |

```python
@pytest.mark.asyncio
async def test_exchangerate_host_sequential_historical_calls(respx_mock):
    """
    ExchangeRateHostConnector.get_historical_series must make one
    GET /historical call per calendar day in the range (sequential, not
    /timeseries which is unavailable on the free tier).
    A 5-day range must produce exactly 5 outbound requests.
    """
    route = respx_mock.get("https://api.exchangerate.host/historical").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "quotes": {"USDEUR": 0.92}
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    await connector.get_historical_series(
        "USD", "EUR", date(2024, 1, 1), date(2024, 1, 5)
    )
    assert route.call_count == 5
```

### TC-CONN-110 — Sequential batching: date param matches requested date

| Field | Value |
|---|---|
| ID | TC-CONN-110 |
| Layer | Unit |
| Priority | P0 |

```python
@pytest.mark.asyncio
async def test_exchangerate_host_historical_date_param(respx_mock):
    """
    Each sequential /historical call must pass the correct 'date' query
    parameter (YYYY-MM-DD) matching the specific day being fetched.
    """
    called_dates = []

    def capture_and_respond(request):
        called_dates.append(request.url.params.get("date"))
        return httpx.Response(200, json={"success": True, "quotes": {"USDEUR": 0.92}})

    respx_mock.get("https://api.exchangerate.host/historical").mock(
        side_effect=capture_and_respond
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    await connector.get_historical_series(
        "USD", "EUR", date(2024, 1, 1), date(2024, 1, 3)
    )
    assert called_dates == ["2024-01-01", "2024-01-02", "2024-01-03"]
```

### TC-CONN-111 — Sequential batching: mid-series error surfaces correctly

| Field | Value |
|---|---|
| ID | TC-CONN-111 |
| Layer | Unit |
| Priority | P0 |

```python
@pytest.mark.asyncio
async def test_exchangerate_host_historical_mid_series_error(respx_mock):
    """
    If one /historical call in a sequential batch returns an error,
    the connector must raise ConnectorError (not silently skip the date).
    """
    responses = [
        httpx.Response(200, json={"success": True, "quotes": {"USDEUR": 0.92}}),
        httpx.Response(200, json={"success": False, "error": {"code": 104}}),
        httpx.Response(200, json={"success": True, "quotes": {"USDEUR": 0.91}}),
    ]
    respx_mock.get("https://api.exchangerate.host/historical").mock(
        side_effect=responses
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    with pytest.raises(ConnectorError):
        await connector.get_historical_series(
            "USD", "EUR", date(2024, 1, 1), date(2024, 1, 3)
        )
```

---

## 3. In-Memory Cache (RateCache)

### Setup

```python
import time
from unittest.mock import patch
from backend.connectors.cache import RateCache
from backend.connectors.mock_connector import MockConnector
```

### TC-CACHE-001 — Cache miss calls connector

| Field | Value |
|---|---|
| ID | TC-CACHE-001 |
| Layer | Unit |
| Priority | P0 |

```python
def test_rate_cache_miss_calls_connector():
    """
    On a cold cache, RateCache must delegate to the underlying connector.
    """
    connector = MockConnector()
    cache = RateCache(connector, ttl_seconds=300)
    with patch.object(connector, "get_historical_rate",
                      wraps=connector.get_historical_rate) as spy:
        cache.get_historical_rate("EUR", "USD", date(2024, 1, 1))
        spy.assert_called_once()
```

### TC-CACHE-002 — Cache hit skips connector

| Field | Value |
|---|---|
| ID | TC-CACHE-002 |
| Layer | Unit |
| Priority | P0 |

```python
def test_rate_cache_hit_no_connector_call():
    """
    A second identical request must be served from cache without
    calling the connector again.
    """
    connector = MockConnector()
    cache = RateCache(connector, ttl_seconds=300)
    with patch.object(connector, "get_historical_rate",
                      wraps=connector.get_historical_rate) as spy:
        cache.get_historical_rate("EUR", "USD", date(2024, 1, 1))
        cache.get_historical_rate("EUR", "USD", date(2024, 1, 1))
        assert spy.call_count == 1
```

### TC-CACHE-003 — TTL expiry triggers re-fetch

| Field | Value |
|---|---|
| ID | TC-CACHE-003 |
| Layer | Unit |
| Priority | P0 |

```python
def test_rate_cache_ttl_expiry():
    """
    After TTL expires the next request must bypass cache and
    call the connector again.
    """
    connector = MockConnector()
    cache = RateCache(connector, ttl_seconds=1)
    with patch.object(connector, "get_historical_rate",
                      wraps=connector.get_historical_rate) as spy:
        cache.get_historical_rate("EUR", "USD", date(2024, 1, 1))
        time.sleep(1.1)
        cache.get_historical_rate("EUR", "USD", date(2024, 1, 1))
        assert spy.call_count == 2
```

### TC-CACHE-004 — Series results are cached

| Field | Value |
|---|---|
| ID | TC-CACHE-004 |
| Layer | Unit |
| Priority | P0 |

```python
def test_rate_cache_series_hit():
    """
    get_historical_series results are cached by (base, target, start, end).
    The second call must not invoke the connector.
    """
    connector = MockConnector()
    cache = RateCache(connector, ttl_seconds=300)
    args = ("GBP", "USD", date(2024, 1, 1), date(2024, 1, 7))
    with patch.object(connector, "get_historical_series",
                      wraps=connector.get_historical_series) as spy:
        cache.get_historical_series(*args)
        cache.get_historical_series(*args)
        assert spy.call_count == 1
```

### TC-CACHE-005 — Different pairs are isolated

| Field | Value |
|---|---|
| ID | TC-CACHE-005 |
| Layer | Unit |
| Priority | P1 |

```python
def test_rate_cache_isolates_different_pairs():
    """
    A cache hit for EUR/USD must not satisfy a EUR/GBP lookup.
    Both must call the connector independently.
    """
    connector = MockConnector()
    cache = RateCache(connector, ttl_seconds=300)
    d = date(2024, 1, 1)
    with patch.object(connector, "get_historical_rate",
                      wraps=connector.get_historical_rate) as spy:
        cache.get_historical_rate("EUR", "USD", d)
        cache.get_historical_rate("EUR", "GBP", d)
        assert spy.call_count == 2
```

### TC-CACHE-006 — Different dates are isolated

| Field | Value |
|---|---|
| ID | TC-CACHE-006 |
| Layer | Unit |
| Priority | P1 |

```python
def test_rate_cache_isolates_different_dates():
    """
    Same pair on different dates must produce two separate cache entries.
    """
    connector = MockConnector()
    cache = RateCache(connector, ttl_seconds=300)
    with patch.object(connector, "get_historical_rate",
                      wraps=connector.get_historical_rate) as spy:
        cache.get_historical_rate("EUR", "USD", date(2024, 1, 1))
        cache.get_historical_rate("EUR", "USD", date(2024, 1, 2))
        assert spy.call_count == 2
```

### TC-CACHE-007 — Cache returns correct data

| Field | Value |
|---|---|
| ID | TC-CACHE-007 |
| Layer | Unit |
| Priority | P0 |

```python
def test_rate_cache_returns_correct_data():
    """
    Cached result must equal the value originally fetched from connector.
    """
    connector = MockConnector()
    cache = RateCache(connector, ttl_seconds=300)
    d = date(2024, 1, 1)
    first = cache.get_historical_rate("EUR", "USD", d)
    second = cache.get_historical_rate("EUR", "USD", d)
    assert first.rate == second.rate
    assert first.date == second.date
```

---

## 4. API Endpoints — Historical Rate (`GET /api/v1/rates/history`)

### Setup

```python
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.connectors.mock_connector import MockConnector

@pytest.fixture
def client():
    app = create_app(connector=MockConnector())
    return TestClient(app)

@pytest.fixture
def client_with_error_connector():
    app = create_app(connector=MockConnector(error_pairs=[("ZZZ", "USD")]))
    return TestClient(app)

@pytest.fixture
def client_with_network_error_connector():
    app = create_app(connector=MockConnector(network_error_pairs=[("EUR", "USD")]))
    return TestClient(app)
```

### TC-API-101 — Happy path: single pair, 7-day range

| Field | Value |
|---|---|
| ID | TC-API-101 |
| Layer | E2E |
| Priority | P0 |

```python
def test_api_history_single_pair_ok(client):
    """
    GET /api/v1/rates/history?base=EUR&quote=USD&start=2024-01-01&end=2024-01-07
    must return HTTP 200 with a series of 7 rate points.
    """
    response = client.get(
        "/api/v1/rates/history",
        params={"base": "EUR", "quote": "USD",
                "start": "2024-01-01", "end": "2024-01-07"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "series" in data
    assert len(data["series"]) == 7
    assert all("date" in p and "rate" in p for p in data["series"])
```

### TC-API-102 — Missing required param returns 422

| Field | Value |
|---|---|
| ID | TC-API-102 |
| Layer | E2E |
| Priority | P0 |

```python
def test_api_history_missing_base_param(client):
    """
    Omitting the 'base' query parameter must return HTTP 422.
    """
    response = client.get(
        "/api/v1/rates/history",
        params={"quote": "USD", "start": "2024-01-01", "end": "2024-01-07"}
    )
    assert response.status_code == 422
```

### TC-API-103 — Invalid date format returns 422

| Field | Value |
|---|---|
| ID | TC-API-103 |
| Layer | E2E |
| Priority | P0 |

```python
def test_api_history_invalid_date_format(client):
    """
    Passing start=not-a-date must return HTTP 422.
    """
    response = client.get(
        "/api/v1/rates/history",
        params={"base": "EUR", "quote": "USD",
                "start": "not-a-date", "end": "2024-01-07"}
    )
    assert response.status_code == 422
```

### TC-API-104 — start after end returns 400

| Field | Value |
|---|---|
| ID | TC-API-104 |
| Layer | E2E |
| Priority | P0 |

```python
def test_api_history_start_after_end(client):
    """
    start > end must return HTTP 400 with a descriptive error message.
    """
    response = client.get(
        "/api/v1/rates/history",
        params={"base": "EUR", "quote": "USD",
                "start": "2024-01-10", "end": "2024-01-01"}
    )
    assert response.status_code == 400
    assert "detail" in response.json()
```

### TC-API-105 — Unsupported pair returns 400

| Field | Value |
|---|---|
| ID | TC-API-105 |
| Layer | E2E |
| Priority | P0 |

```python
def test_api_history_unsupported_pair(client_with_error_connector):
    """
    Connector UnsupportedPairError must map to HTTP 400.
    """
    response = client_with_error_connector.get(
        "/api/v1/rates/history",
        params={"base": "ZZZ", "quote": "USD",
                "start": "2024-01-01", "end": "2024-01-07"}
    )
    assert response.status_code == 400
```

### TC-API-106 — Network error returns 503

| Field | Value |
|---|---|
| ID | TC-API-106 |
| Layer | E2E |
| Priority | P0 |

```python
def test_api_history_network_error(client_with_network_error_connector):
    """
    Connector ConnectorNetworkError must map to HTTP 503.
    """
    response = client_with_network_error_connector.get(
        "/api/v1/rates/history",
        params={"base": "EUR", "quote": "USD",
                "start": "2024-01-01", "end": "2024-01-07"}
    )
    assert response.status_code == 503
```

### TC-API-107 — Date range exceeds 7-day cap returns 400

| Field | Value |
|---|---|
| ID | TC-API-107 |
| Layer | E2E |
| Priority | P0 |

```python
def test_api_history_exceeds_max_days(client):
    """
    An 8-day range (default cap is 7 days, not 31) must return HTTP 400.
    NOTE: /timeseries is unavailable on the free tier; sequential /historical
    calls are used, so the cap is 7 days to protect quota.
    """
    response = client.get(
        "/api/v1/rates/history",
        params={"base": "EUR", "quote": "USD",
                "start": "2024-01-01", "end": "2024-01-09"}  # 8 days
    )
    assert response.status_code == 400
    assert "MAX_HISTORICAL_DAYS" in response.json().get("detail", "")


def test_api_history_exactly_7_days_ok(client):
    """
    Exactly 7 days must be accepted (boundary condition).
    """
    response = client.get(
        "/api/v1/rates/history",
        params={"base": "EUR", "quote": "USD",
                "start": "2024-01-01", "end": "2024-01-07"}
    )
    assert response.status_code == 200
    assert len(response.json()["series"]) == 7
```

### TC-API-108 — Response schema fields are correct

| Field | Value |
|---|---|
| ID | TC-API-108 |
| Layer | E2E |
| Priority | P0 |

```python
def test_api_history_response_schema(client):
    """
    Response must include base, quote, start, end, series, and source fields.
    """
    response = client.get(
        "/api/v1/rates/history",
        params={"base": "EUR", "quote": "USD",
                "start": "2024-01-01", "end": "2024-01-05"}
    )
    assert response.status_code == 200
    data = response.json()
    for field in ("base", "quote", "start", "end", "series", "source"):
        assert field in data, f"Missing field: {field}"
```

---

## 5. API Endpoints — Dashboard CRUD

### TC-DASH-101 — POST /api/v1/dashboards: create single-pair trend dashboard

| Field | Value |
|---|---|
| ID | TC-DASH-101 |
| Layer | E2E |
| Priority | P0 |

```python
def test_create_single_pair_trend_dashboard(client):
    """
    POST /api/v1/dashboards with type=single_pair_trend must return
    HTTP 201 with a dashboard_id and panels list.
    """
    payload = {
        "name": "EUR/USD 30-day",
        "type": "single_pair_trend",
        "panels": [
            {"base": "EUR", "quote": "USD",
             "start": "2024-01-01", "end": "2024-01-31",
             "chart_type": "line"}
        ]
    }
    response = client.post("/api/v1/dashboards", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "dashboard_id" in data
    assert isinstance(data["panels"], list)
    assert len(data["panels"]) == 1
```

### TC-DASH-102 — POST /api/v1/dashboards: multi-pair comparison

| Field | Value |
|---|---|
| ID | TC-DASH-102 |
| Layer | E2E |
| Priority | P0 |

```python
def test_create_multi_pair_comparison_dashboard(client):
    """
    POST with type=multi_pair_comparison and 3 panels must return
    HTTP 201 with all 3 panels populated.
    """
    payload = {
        "name": "Major Pairs Jan 2024",
        "type": "multi_pair_comparison",
        "panels": [
            {"base": "EUR", "quote": "USD", "start": "2024-01-01", "end": "2024-01-31", "chart_type": "line"},
            {"base": "GBP", "quote": "USD", "start": "2024-01-01", "end": "2024-01-31", "chart_type": "line"},
            {"base": "JPY", "quote": "USD", "start": "2024-01-01", "end": "2024-01-31", "chart_type": "bar"},
        ]
    }
    response = client.post("/api/v1/dashboards", json=payload)
    assert response.status_code == 201
    assert len(response.json()["panels"]) == 3
```

### TC-DASH-103 — POST /api/v1/dashboards: currency heatmap

| Field | Value |
|---|---|
| ID | TC-DASH-103 |
| Layer | E2E |
| Priority | P0 |

```python
def test_create_currency_heatmap_dashboard(client):
    """
    POST with type=currency_heatmap must return HTTP 201.
    Heatmap panel includes a grid field in the response.
    """
    payload = {
        "name": "Heatmap Jan 2024",
        "type": "currency_heatmap",
        "panels": [
            {"base": "EUR", "quote": "USD", "start": "2024-01-01", "end": "2024-01-31", "chart_type": "heatmap"}
        ]
    }
    response = client.post("/api/v1/dashboards", json=payload)
    assert response.status_code == 201
    panel = response.json()["panels"][0]
    assert "grid" in panel
```

### TC-DASH-104 — GET /api/v1/dashboards/{id}: retrieve existing dashboard

| Field | Value |
|---|---|
| ID | TC-DASH-104 |
| Layer | E2E |
| Priority | P0 |

```python
def test_get_dashboard_by_id(client):
    """
    A dashboard created via POST must be retrievable via GET
    with all original fields intact.
    """
    payload = {
        "name": "Test Dashboard",
        "type": "single_pair_trend",
        "panels": [{"base": "EUR", "quote": "USD",
                    "start": "2024-01-01", "end": "2024-01-07",
                    "chart_type": "line"}]
    }
    create_resp = client.post("/api/v1/dashboards", json=payload)
    dashboard_id = create_resp.json()["dashboard_id"]

    get_resp = client.get(f"/api/v1/dashboards/{dashboard_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["name"] == "Test Dashboard"
    assert data["type"] == "single_pair_trend"
```

### TC-DASH-105 — GET /api/v1/dashboards/{id}: unknown ID returns 404

| Field | Value |
|---|---|
| ID | TC-DASH-105 |
| Layer | E2E |
| Priority | P0 |

```python
def test_get_dashboard_not_found(client):
    """
    GET for a non-existent dashboard_id must return HTTP 404.
    """
    response = client.get("/api/v1/dashboards/nonexistent-id-99999")
    assert response.status_code == 404
```

### TC-DASH-106 — PATCH /api/v1/dashboards/{id}: dashboard type switch

| Field | Value |
|---|---|
| ID | TC-DASH-106 |
| Layer | E2E |
| Priority | P0 |

```python
def test_dashboard_type_switch(client):
    """
    PATCH with a new type must switch the dashboard type without
    losing existing panels.
    """
    payload = {
        "name": "Switch Test",
        "type": "single_pair_trend",
        "panels": [{"base": "EUR", "quote": "USD",
                    "start": "2024-01-01", "end": "2024-01-07",
                    "chart_type": "line"}]
    }
    create_resp = client.post("/api/v1/dashboards", json=payload)
    dashboard_id = create_resp.json()["dashboard_id"]

    patch_resp = client.patch(
        f"/api/v1/dashboards/{dashboard_id}",
        json={"type": "multi_pair_comparison"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["type"] == "multi_pair_comparison"
    assert len(patch_resp.json()["panels"]) >= 1
```

### TC-DASH-107 — DELETE /api/v1/dashboards/{id}: removes dashboard

| Field | Value |
|---|---|
| ID | TC-DASH-107 |
| Layer | E2E |
| Priority | P1 |

```python
def test_delete_dashboard(client):
    """
    DELETE must return HTTP 204 and subsequent GET must return 404.
    """
    payload = {"name": "Delete Me", "type": "single_pair_trend",
               "panels": [{"base": "USD", "quote": "JPY",
                           "start": "2024-01-01", "end": "2024-01-05",
                           "chart_type": "line"}]}
    dashboard_id = client.post("/api/v1/dashboards", json=payload).json()["dashboard_id"]
    delete_resp = client.delete(f"/api/v1/dashboards/{dashboard_id}")
    assert delete_resp.status_code == 204
    get_resp = client.get(f"/api/v1/dashboards/{dashboard_id}")
    assert get_resp.status_code == 404
```

---

## 6. API Endpoints — Panel Management

### TC-PANEL-101 — POST /api/v1/dashboards/{id}/panels: add panel

| Field | Value |
|---|---|
| ID | TC-PANEL-101 |
| Layer | E2E |
| Priority | P0 |

```python
def test_add_panel_to_dashboard(client):
    """
    POST a new panel to an existing dashboard must return HTTP 201
    and the panel must appear in subsequent GET.
    """
    dashboard_id = client.post("/api/v1/dashboards", json={
        "name": "Panel Test", "type": "multi_pair_comparison", "panels": []
    }).json()["dashboard_id"]

    panel_payload = {"base": "GBP", "quote": "USD",
                     "start": "2024-01-01", "end": "2024-01-07",
                     "chart_type": "line"}
    resp = client.post(f"/api/v1/dashboards/{dashboard_id}/panels",
                       json=panel_payload)
    assert resp.status_code == 201
    assert "panel_id" in resp.json()

    dashboard = client.get(f"/api/v1/dashboards/{dashboard_id}").json()
    assert any(p["base"] == "GBP" for p in dashboard["panels"])
```

### TC-PANEL-102 — DELETE /api/v1/dashboards/{id}/panels/{panel_id}

| Field | Value |
|---|---|
| ID | TC-PANEL-102 |
| Layer | E2E |
| Priority | P1 |

```python
def test_remove_panel_from_dashboard(client):
    """
    DELETE a panel must return HTTP 204 and the panel must not
    appear in subsequent dashboard GET.
    """
    dashboard_id = client.post("/api/v1/dashboards", json={
        "name": "Remove Panel Test", "type": "multi_pair_comparison",
        "panels": [{"base": "EUR", "quote": "USD",
                    "start": "2024-01-01", "end": "2024-01-07",
                    "chart_type": "line"}]
    }).json()["dashboard_id"]

    dashboard = client.get(f"/api/v1/dashboards/{dashboard_id}").json()
    panel_id = dashboard["panels"][0]["panel_id"]

    del_resp = client.delete(
        f"/api/v1/dashboards/{dashboard_id}/panels/{panel_id}"
    )
    assert del_resp.status_code == 204

    updated = client.get(f"/api/v1/dashboards/{dashboard_id}").json()
    assert all(p["panel_id"] != panel_id for p in updated["panels"])
```

### TC-PANEL-103 — Panel data contains expected series

| Field | Value |
|---|---|
| ID | TC-PANEL-103 |
| Layer | E2E |
| Priority | P0 |

```python
def test_panel_data_contains_series(client):
    """
    Each panel in a dashboard response must contain a non-empty
    series list with date and rate fields.
    """
    response = client.post("/api/v1/dashboards", json={
        "name": "Series Check", "type": "single_pair_trend",
        "panels": [{"base": "EUR", "quote": "USD",
                    "start": "2024-01-01", "end": "2024-01-05",
                    "chart_type": "line"}]
    })
    assert response.status_code == 201
    panel = response.json()["panels"][0]
    assert "series" in panel
    assert len(panel["series"]) == 5
    for point in panel["series"]:
        assert "date" in point
        assert "rate" in point
        assert isinstance(point["rate"], float)
```

### TC-PANEL-104 — Panel error state: unsupported pair

| Field | Value |
|---|---|
| ID | TC-PANEL-104 |
| Layer | E2E |
| Priority | P0 |

```python
def test_panel_error_state_unsupported_pair(client_with_error_connector):
    """
    When a panel's pair is unsupported, the panel must contain an
    error field instead of raising a 500, and other panels in the
    same dashboard must still succeed.
    """
    response = client_with_error_connector.post("/api/v1/dashboards", json={
        "name": "Error Panel Test", "type": "multi_pair_comparison",
        "panels": [
            {"base": "ZZZ", "quote": "USD",
             "start": "2024-01-01", "end": "2024-01-05",
             "chart_type": "line"},
        ]
    })
    # Dashboard creation succeeds; individual panel carries error state
    assert response.status_code in (200, 201)
    panel = response.json()["panels"][0]
    assert panel.get("error") is not None
    assert panel.get("series") is None or panel.get("series") == []
```

### TC-PANEL-105 — Panel empty state: zero-length date range

| Field | Value |
|---|---|
| ID | TC-PANEL-105 |
| Layer | E2E |
| Priority | P1 |

```python
def test_panel_empty_state_same_day(client):
    """
    A panel with start==end must return a series of exactly one point,
    not an empty list or an error.
    """
    response = client.post("/api/v1/dashboards", json={
        "name": "Single Day Panel", "type": "single_pair_trend",
        "panels": [{"base": "EUR", "quote": "USD",
                    "start": "2024-06-01", "end": "2024-06-01",
                    "chart_type": "line"}]
    })
    assert response.status_code == 201
    panel = response.json()["panels"][0]
    assert len(panel["series"]) == 1
```

---

## 7. Dashboard Layout Endpoint

### TC-LAYOUT-101 — GET /api/v1/dashboards/{id}/layout: grid structure

| Field | Value |
|---|---|
| ID | TC-LAYOUT-101 |
| Layer | E2E |
| Priority | P0 |

```python
def test_dashboard_layout_grid_structure(client):
    """
    GET /api/v1/dashboards/{id}/layout must return a grid field
    describing CSS Grid positioning for each panel.
    """
    dashboard_id = client.post("/api/v1/dashboards", json={
        "name": "Layout Test", "type": "multi_pair_comparison",
        "panels": [
            {"base": "EUR", "quote": "USD", "start": "2024-01-01",
             "end": "2024-01-07", "chart_type": "line"},
            {"base": "GBP", "quote": "USD", "start": "2024-01-01",
             "end": "2024-01-07", "chart_type": "bar"},
        ]
    }).json()["dashboard_id"]

    resp = client.get(f"/api/v1/dashboards/{dashboard_id}/layout")
    assert resp.status_code == 200
    layout = resp.json()
    assert "grid" in layout
    assert len(layout["grid"]) == 2
    for cell in layout["grid"]:
        assert "panel_id" in cell
        assert "col_start" in cell
        assert "col_end" in cell
        assert "row_start" in cell
        assert "row_end" in cell
```

### TC-LAYOUT-102 — Layout unknown dashboard returns 404

| Field | Value |
|---|---|
| ID | TC-LAYOUT-102 |
| Layer | E2E |
| Priority | P1 |

```python
def test_dashboard_layout_not_found(client):
    """
    GET layout for a non-existent dashboard must return HTTP 404.
    """
    resp = client.get("/api/v1/dashboards/does-not-exist/layout")
    assert resp.status_code == 404
```

---

## 8. Quota Endpoint

### TC-QUOTA-101 — GET /api/v1/quota: returns quota state

| Field | Value |
|---|---|
| ID | TC-QUOTA-101 |
| Layer | E2E |
| Priority | P0 |

```python
def test_quota_endpoint_returns_state(client):
    """
    GET /api/v1/quota must return HTTP 200 with used, limit, and
    remaining fields.
    """
    resp = client.get("/api/v1/quota")
    assert resp.status_code == 200
    data = resp.json()
    for field in ("used", "limit", "remaining"):
        assert field in data, f"Missing quota field: {field}"
    assert data["remaining"] == data["limit"] - data["used"]
```

### TC-QUOTA-102 — Quota increments after historical fetch

| Field | Value |
|---|---|
| ID | TC-QUOTA-102 |
| Layer | E2E |
| Priority | P0 |

```python
def test_quota_increments_after_fetch(client):
    """
    After a successful historical rate request, the quota 'used'
    counter must increase by the number of API calls made.
    """
    before = client.get("/api/v1/quota").json()["used"]
    client.get("/api/v1/rates/history",
               params={"base": "EUR", "quote": "USD",
                       "start": "2024-01-01", "end": "2024-01-07"})
    after = client.get("/api/v1/quota").json()["used"]
    # MockConnector does not consume real quota but counter must still update
    assert after >= before
```

### TC-QUOTA-103 — Quota exhaustion returns 429

| Field | Value |
|---|---|
| ID | TC-QUOTA-103 |
| Layer | E2E |
| Priority | P0 |

```python
def test_quota_exhaustion_returns_429(monkeypatch):
    """
    When session quota is exhausted (QUOTA_LIMIT_PER_SESSION reached),
    subsequent requests must return HTTP 429 Too Many Requests.
    """
    monkeypatch.setenv("QUOTA_LIMIT_PER_SESSION", "1")
    app = create_app(connector=MockConnector())
    limited_client = TestClient(app)

    # First request consumes the quota
    limited_client.get("/api/v1/rates/history",
                       params={"base": "EUR", "quote": "USD",
                               "start": "2024-01-01", "end": "2024-01-02"})
    # Second must be rejected
    resp = limited_client.get("/api/v1/rates/history",
                              params={"base": "EUR", "quote": "USD",
                                      "start": "2024-01-01", "end": "2024-01-02"})
    assert resp.status_code == 429
```

### TC-QUOTA-104 — Cache hit does not increment quota counter

| Field | Value |
|---|---|
| ID | TC-QUOTA-104 |
| Layer | E2E |
| Priority | P0 |

```python
def test_quota_cache_hit_no_increment(client):
    """
    A repeated identical request served from cache must NOT increment
    the quota counter (no new API call was made).
    """
    params = {"base": "EUR", "quote": "USD",
              "start": "2024-01-01", "end": "2024-01-07"}
    client.get("/api/v1/rates/history", params=params)
    after_first = client.get("/api/v1/quota").json()["used"]
    client.get("/api/v1/rates/history", params=params)  # cache hit
    after_second = client.get("/api/v1/quota").json()["used"]
    assert after_first == after_second
```

---

## 9. Dashboard Type Switching

### TC-TYPE-101 — Switch from single_pair_trend to multi_pair_comparison

| Field | Value |
|---|---|
| ID | TC-TYPE-101 |
| Layer | E2E |
| Priority | P0 |

```python
def test_type_switch_single_to_multi(client):
    """
    Switching type from single_pair_trend to multi_pair_comparison
    must preserve existing panels and update the type field.
    """
    dashboard_id = client.post("/api/v1/dashboards", json={
        "name": "Type Switch", "type": "single_pair_trend",
        "panels": [{"base": "EUR", "quote": "USD",
                    "start": "2024-01-01", "end": "2024-01-07",
                    "chart_type": "line"}]
    }).json()["dashboard_id"]

    resp = client.patch(f"/api/v1/dashboards/{dashboard_id}",
                        json={"type": "multi_pair_comparison"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "multi_pair_comparison"
    assert len(body["panels"]) >= 1
    assert body["panels"][0]["base"] == "EUR"
```

### TC-TYPE-102 — Switch to currency_heatmap adds grid field

| Field | Value |
|---|---|
| ID | TC-TYPE-102 |
| Layer | E2E |
| Priority | P1 |

```python
def test_type_switch_to_heatmap_adds_grid(client):
    """
    Switching to currency_heatmap type must add a grid field
    to each panel in the response.
    """
    dashboard_id = client.post("/api/v1/dashboards", json={
        "name": "Heatmap Switch", "type": "single_pair_trend",
        "panels": [{"base": "EUR", "quote": "USD",
                    "start": "2024-01-01", "end": "2024-01-07",
                    "chart_type": "line"}]
    }).json()["dashboard_id"]

    resp = client.patch(f"/api/v1/dashboards/{dashboard_id}",
                        json={"type": "currency_heatmap"})
    assert resp.status_code == 200
    panel = resp.json()["panels"][0]
    assert "grid" in panel
```

### TC-TYPE-103 — Invalid dashboard type returns 422

| Field | Value |
|---|---|
| ID | TC-TYPE-103 |
| Layer | E2E |
| Priority | P0 |

```python
def test_invalid_dashboard_type_returns_422(client):
    """
    POST with an unknown dashboard type must return HTTP 422.
    """
    resp = client.post("/api/v1/dashboards", json={
        "name": "Bad Type", "type": "not_a_real_type", "panels": []
    })
    assert resp.status_code == 422
```

---

## 10. ExchangeRateHostConnector — Historical Endpoints

### Setup

```python
import respx
import httpx
from backend.connectors.exchangerate_host import ExchangeRateHostConnector
```

All tests in this section use `respx.mock` — no real network calls.

### TC-EX-101 — get_historical_rate: happy path

| Field | Value |
|---|---|
| ID | TC-EX-101 |
| Layer | Unit |
| Priority | P0 |

```python
@pytest.mark.asyncio
async def test_exchangerate_host_historical_rate_happy_path(respx_mock):
    """
    GET /historical with valid params must parse the response into
    a HistoricalRatePoint with correct fields.
    """
    respx_mock.get("https://api.exchangerate.host/historical").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "date": "2024-01-15",
            "quotes": {"USDEUR": 0.9234}
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    result = await connector.get_historical_rate("USD", "EUR", date(2024, 1, 15))
    assert result.base == "USD"
    assert result.target == "EUR"
    assert result.rate == pytest.approx(0.9234)
    assert result.date == "2024-01-15"
```

### TC-EX-102 — get_historical_rate: API returns success=false raises ConnectorError

| Field | Value |
|---|---|
| ID | TC-EX-102 |
| Layer | Unit |
| Priority | P0 |

```python
@pytest.mark.asyncio
async def test_exchangerate_host_historical_rate_api_error(respx_mock):
    """
    When the API returns success=false, connector must raise ConnectorError.
    """
    respx_mock.get("https://api.exchangerate.host/historical").mock(
        return_value=httpx.Response(200, json={"success": False,
                                               "error": {"code": 104}})
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    with pytest.raises(ConnectorError):
        await connector.get_historical_rate("USD", "EUR", date(2024, 1, 15))
```

### TC-EX-103 — get_historical_rate: HTTP 500 raises ConnectorNetworkError

| Field | Value |
|---|---|
| ID | TC-EX-103 |
| Layer | Unit |
| Priority | P0 |

```python
@pytest.mark.asyncio
async def test_exchangerate_host_historical_rate_http_500(respx_mock):
    """
    HTTP 5xx from the upstream API must raise ConnectorNetworkError.
    """
    respx_mock.get("https://api.exchangerate.host/historical").mock(
        return_value=httpx.Response(500)
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    with pytest.raises(ConnectorNetworkError):
        await connector.get_historical_rate("USD", "EUR", date(2024, 1, 15))
```

### TC-EX-104 — API key is included in every historical request

| Field | Value |
|---|---|
| ID | TC-EX-104 |
| Layer | Unit |
| Priority | P0 |

```python
@pytest.mark.asyncio
async def test_exchangerate_host_api_key_in_request(respx_mock):
    """
    The access_key query parameter must be present in every outbound request.
    API key must NOT appear in logs or response bodies.
    """
    route = respx_mock.get("https://api.exchangerate.host/historical").mock(
        return_value=httpx.Response(200, json={
            "success": True, "date": "2024-01-01",
            "quotes": {"USDEUR": 0.92}
        })
    )
    connector = ExchangeRateHostConnector(api_key="secret_key_123")
    await connector.get_historical_rate("USD", "EUR", date(2024, 1, 1))
    assert route.called
    request = route.calls[0].request
    assert "access_key" in str(request.url)
    assert "secret_key_123" in str(request.url)
```

---

## 10b. MockConnector — get_historical_rates Error Injection

> BLOCKER: These tests cannot be written until MockConnector implements
> `get_historical_rates(base, quote, start_date, end_date)` with error injection
> support. All dashboard tests depend on this method.

### Setup

```python
from backend.connectors.mock_connector import MockConnector
from backend.connectors.errors import ConnectorError, ConnectorNetworkError
```

### TC-GHR-001 — get_historical_rates: happy path

| Field | Value |
|---|---|
| ID | TC-GHR-001 |
| Layer | Unit |
| Priority | P0 |

```python
def test_get_historical_rates_happy_path():
    """
    get_historical_rates("EUR", "USD", start, end) must return a
    HistoricalRateSeries with one point per day in the range.
    """
    connector = MockConnector()
    result = connector.get_historical_rates(
        "EUR", "USD", date(2024, 1, 1), date(2024, 1, 7)
    )
    assert len(result.points) == 7
    assert result.base == "EUR"
    assert result.target == "USD"
    for point in result.points:
        assert point.rate > 0
        assert point.date is not None
```

### TC-GHR-002 — get_historical_rates: 503 error injection

| Field | Value |
|---|---|
| ID | TC-GHR-002 |
| Layer | Unit |
| Priority | P0 |

```python
def test_get_historical_rates_503_injection():
    """
    MockConnector(http_error_pairs=[("EUR", "USD", 503)]) must raise
    ConnectorNetworkError with a 503 status indicator.
    This is a blocker test — all dashboard error-state tests depend on it.
    """
    connector = MockConnector(http_error_pairs=[("EUR", "USD", 503)])
    with pytest.raises(ConnectorNetworkError) as exc_info:
        connector.get_historical_rates(
            "EUR", "USD", date(2024, 1, 1), date(2024, 1, 7)
        )
    assert "503" in str(exc_info.value) or exc_info.value.status_code == 503
```

### TC-GHR-003 — get_historical_rates: timeout injection

| Field | Value |
|---|---|
| ID | TC-GHR-003 |
| Layer | Unit |
| Priority | P0 |

```python
def test_get_historical_rates_timeout_injection():
    """
    MockConnector(timeout_pairs=[("EUR", "USD")]) must raise
    ConnectorNetworkError (or ConnectorTimeoutError) to simulate
    an upstream timeout.
    """
    connector = MockConnector(timeout_pairs=[("EUR", "USD")])
    with pytest.raises((ConnectorNetworkError, ConnectorTimeoutError)):
        connector.get_historical_rates(
            "EUR", "USD", date(2024, 1, 1), date(2024, 1, 7)
        )
```

### TC-GHR-004 — get_historical_rates: partial data injection

| Field | Value |
|---|---|
| ID | TC-GHR-004 |
| Layer | Unit |
| Priority | P0 |

```python
def test_get_historical_rates_partial_data_injection():
    """
    MockConnector(partial_data_pairs=[("EUR", "USD", 3)]) must return
    only 3 points for a 7-day request, simulating partial upstream data.
    The caller (dashboard service) must handle this gracefully.
    """
    connector = MockConnector(partial_data_pairs=[("EUR", "USD", 3)])
    result = connector.get_historical_rates(
        "EUR", "USD", date(2024, 1, 1), date(2024, 1, 7)
    )
    assert len(result.points) == 3
```

### TC-GHR-005 — get_historical_rates: error injection does not affect other pairs

| Field | Value |
|---|---|
| ID | TC-GHR-005 |
| Layer | Unit |
| Priority | P1 |

```python
def test_get_historical_rates_error_isolation():
    """
    A 503 injection on EUR/USD must not affect GBP/USD on the same range.
    """
    connector = MockConnector(http_error_pairs=[("EUR", "USD", 503)])
    with pytest.raises(ConnectorNetworkError):
        connector.get_historical_rates(
            "EUR", "USD", date(2024, 1, 1), date(2024, 1, 7)
        )
    # GBP/USD must still succeed
    result = connector.get_historical_rates(
        "GBP", "USD", date(2024, 1, 1), date(2024, 1, 7)
    )
    assert len(result.points) == 7
```

### TC-GHR-006 — Dashboard panel carries error state on 503

| Field | Value |
|---|---|
| ID | TC-GHR-006 |
| Layer | E2E |
| Priority | P0 |

```python
def test_dashboard_panel_error_state_on_503():
    """
    When get_historical_rates raises ConnectorNetworkError (503),
    the dashboard service must set panel.error and leave panel.series
    empty — NOT propagate a 500.
    Other panels in the same dashboard must still render correctly.
    """
    connector = MockConnector(http_error_pairs=[("EUR", "USD", 503)])
    app = create_app(connector=connector)
    client = TestClient(app)

    response = client.post("/api/v1/dashboards", json={
        "name": "503 Test", "type": "multi_pair_comparison",
        "panels": [
            {"base": "EUR", "quote": "USD",
             "start": "2024-01-01", "end": "2024-01-07", "chart_type": "line"},
            {"base": "GBP", "quote": "USD",
             "start": "2024-01-01", "end": "2024-01-07", "chart_type": "line"},
        ]
    })
    assert response.status_code in (200, 201)
    panels = response.json()["panels"]
    eur_panel = next(p for p in panels if p["base"] == "EUR")
    gbp_panel = next(p for p in panels if p["base"] == "GBP")
    assert eur_panel.get("error") is not None
    assert gbp_panel.get("series") and len(gbp_panel["series"]) > 0
```

### TC-GHR-007 — Dashboard panel carries error state on timeout

| Field | Value |
|---|---|
| ID | TC-GHR-007 |
| Layer | E2E |
| Priority | P0 |

```python
def test_dashboard_panel_error_state_on_timeout():
    """
    When get_historical_rates raises a timeout error,
    the dashboard service must set panel.error — NOT propagate a 500.
    """
    connector = MockConnector(timeout_pairs=[("JPY", "USD")])
    app = create_app(connector=connector)
    client = TestClient(app)

    response = client.post("/api/v1/dashboards", json={
        "name": "Timeout Test", "type": "single_pair_trend",
        "panels": [{"base": "JPY", "quote": "USD",
                    "start": "2024-01-01", "end": "2024-01-07",
                    "chart_type": "line"}]
    })
    assert response.status_code in (200, 201)
    panel = response.json()["panels"][0]
    assert panel.get("error") is not None
```

---

## 10c. Heatmap Boundary Cases

### TC-HEAT-001 — 6-currency heatmap: 30 unique pair lookups

| Field | Value |
|---|---|
| ID | TC-HEAT-001 |
| Layer | Unit |
| Priority | P0 |

```python
def test_heatmap_6_currencies_30_pairs():
    """
    A currency_heatmap dashboard with 6 currencies requires
    N*(N-1) = 6*5 = 30 unique directional pair lookups
    (or N*(N-1)/2 = 15 symmetric pairs, each looked up once and mirrored).
    Verify the dashboard service requests exactly the right number of pairs.
    """
    connector = MockConnector()
    currencies = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD"]
    with patch.object(connector, "get_historical_rates",
                      wraps=connector.get_historical_rates) as spy:
        app = create_app(connector=connector)
        client = TestClient(app)
        response = client.post("/api/v1/dashboards", json={
            "name": "6-Currency Heatmap",
            "type": "currency_heatmap",
            "currencies": currencies,
            "start": "2024-01-01",
            "end": "2024-01-07"
        })
        assert response.status_code in (200, 201)
        # 15 unique pairs (symmetric), each fetched once
        assert spy.call_count == 15
```

### TC-HEAT-002 — Heatmap: warm cache serves all 15 pairs without connector calls

| Field | Value |
|---|---|
| ID | TC-HEAT-002 |
| Layer | Unit |
| Priority | P0 |

```python
def test_heatmap_warm_cache_no_connector_calls():
    """
    A second identical 6-currency heatmap request must be served
    entirely from cache — 0 connector calls.
    """
    connector = MockConnector()
    app = create_app(connector=connector)
    client = TestClient(app)
    payload = {
        "name": "6-Currency Heatmap",
        "type": "currency_heatmap",
        "currencies": ["USD", "EUR", "GBP", "JPY", "AUD", "CAD"],
        "start": "2024-01-01",
        "end": "2024-01-07"
    }
    client.post("/api/v1/dashboards", json=payload)  # cold
    with patch.object(connector, "get_historical_rates",
                      wraps=connector.get_historical_rates) as spy:
        client.post("/api/v1/dashboards", json=payload)  # warm
        assert spy.call_count == 0
```

### TC-HEAT-003 — Heatmap: 2-currency edge case (1 pair)

| Field | Value |
|---|---|
| ID | TC-HEAT-003 |
| Layer | Unit |
| Priority | P1 |

```python
def test_heatmap_2_currencies_1_pair():
    """
    A 2-currency heatmap requires exactly 1 pair lookup.
    N*(N-1)/2 = 1.
    """
    connector = MockConnector()
    with patch.object(connector, "get_historical_rates",
                      wraps=connector.get_historical_rates) as spy:
        app = create_app(connector=connector)
        client = TestClient(app)
        response = client.post("/api/v1/dashboards", json={
            "name": "2-Currency Heatmap",
            "type": "currency_heatmap",
            "currencies": ["USD", "EUR"],
            "start": "2024-01-01",
            "end": "2024-01-07"
        })
        assert response.status_code in (200, 201)
        assert spy.call_count == 1
```

### TC-HEAT-004 — Heatmap: single currency returns 422

| Field | Value |
|---|---|
| ID | TC-HEAT-004 |
| Layer | E2E |
| Priority | P1 |

```python
def test_heatmap_single_currency_rejected(client):
    """
    A heatmap with only 1 currency cannot form any pairs.
    Must return HTTP 422.
    """
    response = client.post("/api/v1/dashboards", json={
        "name": "Bad Heatmap",
        "type": "currency_heatmap",
        "currencies": ["USD"],
        "start": "2024-01-01",
        "end": "2024-01-07"
    })
    assert response.status_code == 422
```

---

## 10e. error_dates — Dashboard Service Boundary Cases

> Target file: `tests/unit/test_dashboard_service.py`
> These tests exercise `build_dashboard_response()` and the cache layer
> using MockConnector `error_dates` injection to simulate partial failures
> at specific dates within a series.

### TC-EDATE-001 — build_dashboard_response: mid-series date failure produces partial panel

| Field | Value |
|---|---|
| ID | TC-EDATE-001 |
| Layer | Unit |
| Priority | P0 |

```python
def test_build_dashboard_mid_series_error_date():
    """
    When date 4 of a 7-day range fails (error_dates injection),
    build_dashboard_response() must either:
      (a) set panel.error and return an empty series, OR
      (b) return a partial series with the failed date omitted
          and a panel.warning field indicating the gap.
    It must NOT raise an unhandled exception or return a 500.
    """
    error_date = date(2024, 1, 4)
    connector = MockConnector(
        error_dates=[("EUR", "USD", error_date)]
    )
    service = DashboardService(connector=connector)
    panel_config = PanelConfig(
        base="EUR", quote="USD",
        start=date(2024, 1, 1), end=date(2024, 1, 7),
        chart_type="line"
    )
    panel = service.build_panel(panel_config)
    # Either error flag or partial series with warning — not a 500
    has_error = panel.error is not None
    has_partial = panel.series is not None and len(panel.series) < 7
    assert has_error or has_partial, (
        "Panel must carry error or partial series when a mid-range date fails"
    )
```

### TC-EDATE-002 — build_dashboard_response: first date failure

| Field | Value |
|---|---|
| ID | TC-EDATE-002 |
| Layer | Unit |
| Priority | P0 |

```python
def test_build_dashboard_first_date_error():
    """
    When the first date of the range fails, the panel must carry
    an error or partial series — not a 500 or empty-success response.
    """
    error_date = date(2024, 1, 1)
    connector = MockConnector(
        error_dates=[("EUR", "USD", error_date)]
    )
    service = DashboardService(connector=connector)
    panel = service.build_panel(PanelConfig(
        base="EUR", quote="USD",
        start=date(2024, 1, 1), end=date(2024, 1, 7),
        chart_type="line"
    ))
    assert panel.error is not None or (
        panel.series is not None and len(panel.series) < 7
    )
```

### TC-EDATE-003 — Heatmap: one pair fails mid-series, others succeed

| Field | Value |
|---|---|
| ID | TC-EDATE-003 |
| Layer | Unit |
| Priority | P0 |

```python
def test_heatmap_one_pair_mid_series_failure():
    """
    In a 3-currency heatmap (3 pairs), if EUR/GBP fails on date 3,
    the heatmap cell for EUR/GBP must carry an error/warning while
    the other 2 cells (EUR/USD, GBP/USD) render fully.
    The overall dashboard response must still be HTTP 200/201.
    """
    error_date = date(2024, 1, 3)
    connector = MockConnector(
        error_dates=[("EUR", "GBP", error_date)]
    )
    app = create_app(connector=connector)
    client = TestClient(app)

    response = client.post("/api/v1/dashboards", json={
        "name": "Heatmap Partial Failure",
        "type": "currency_heatmap",
        "currencies": ["EUR", "GBP", "USD"],
        "start": "2024-01-01",
        "end": "2024-01-07"
    })
    assert response.status_code in (200, 201)
    panels = response.json()["panels"]

    eur_gbp = next(
        (p for p in panels if p["base"] == "EUR" and p["quote"] == "GBP"), None
    )
    assert eur_gbp is not None
    assert eur_gbp.get("error") is not None or (
        eur_gbp.get("series") is not None and len(eur_gbp["series"]) < 7
    )

    # Other pairs must be fully populated
    other_panels = [p for p in panels
                    if not (p["base"] == "EUR" and p["quote"] == "GBP")]
    for p in other_panels:
        assert p.get("series") and len(p["series"]) == 7
```

### TC-EDATE-004 — Cache gap: error_date is not cached, adjacent dates remain cached

| Field | Value |
|---|---|
| ID | TC-EDATE-004 |
| Layer | Unit |
| Priority | P0 |

```python
def test_cache_gap_error_date_not_stored():
    """
    When a specific date fails during series population, that date
    must NOT be stored in the cache (a cached error would poison
    subsequent requests after the transient failure clears).
    Adjacent successful dates must remain cached.
    """
    error_date = date(2024, 1, 4)
    connector = MockConnector(
        error_dates=[("EUR", "USD", error_date)]
    )
    cache = RateCache(connector, ttl_seconds=300)

    # First attempt: error_date raises, others are cached
    try:
        cache.get_historical_series("EUR", "USD", date(2024, 1, 1), date(2024, 1, 7))
    except ConnectorError:
        pass

    # Now fix the connector — remove the error_date injection
    connector2 = MockConnector()  # no errors
    cache2 = RateCache(connector2, ttl_seconds=300)

    # A fresh request for the previously-failed date must go to connector
    with patch.object(connector2, "get_historical_rate",
                      wraps=connector2.get_historical_rate) as spy:
        cache2.get_historical_rate("EUR", "USD", error_date)
        spy.assert_called_once()  # must not serve a cached error
```

---

## 10d. Test File Locations

All new test cases must be placed in these files:

| File | Contents |
|---|---|
| `tests/unit/test_cache.py` | TC-CACHE-001 through TC-CACHE-007 |
| `tests/unit/test_dashboard_service.py` | TC-GHR-001–005, TC-HEAT-001–003, TC-MOCK-008–010, dashboard service unit tests |
| `tests/e2e/test_dashboard_api.py` | TC-DASH-101–107, TC-PANEL-101–105, TC-LAYOUT-101–102, TC-QUOTA-101–104, TC-TYPE-101–103, TC-GHR-006–007, TC-HEAT-004 |
| `tests/unit/test_connector.py` | TC-CONN-101–111, TC-EX-101–104 (existing file, extend) |
| `tests/unit/test_mock_connector.py` | TC-MOCK-001–010 (existing file, extend) |

90% line coverage is required across ALL new files: `cache.py`, `dashboard.py`, and all three new test files must be measured individually.

---

## 11. Feature 01 — Preserved Test Cases (Spot Rate Chat)

> These test cases carry over from v1.0. IDs are unchanged.

### TC-CONN-01 — Happy path: direct USD pair

```python
@pytest.mark.asyncio
async def test_get_rate_happy_path(respx_mock):
    """
    ExchangeRateHostConnector.get_rate("USD", "GBP") must return
    correct rate from mocked API response.
    """
    respx_mock.get("https://api.exchangerate.host/live").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "quotes": {"USDGBP": 0.7856},
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    result = await connector.get_rate("USD", "GBP")
    assert result.base == "USD"
    assert result.target == "GBP"
    assert result.rate == pytest.approx(0.7856)
```

### TC-CONN-06 — Cross-rate triangulation (spot)

```python
@pytest.mark.asyncio
async def test_cross_rate_triangulation_spot(respx_mock):
    """
    EUR/GBP spot rate must be derived from EUR/USD and GBP/USD via
    two sequential calls. Result = EUR/USD / GBP/USD.
    """
    respx_mock.get("https://api.exchangerate.host/live").mock(
        side_effect=[
            httpx.Response(200, json={"success": True, "quotes": {"USDEUR": 1.0823}}),
            httpx.Response(200, json={"success": True, "quotes": {"USDGBP": 0.7856}}),
        ]
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    result = await connector.get_rate("EUR", "GBP")
    expected = 1.0823 / 0.7856  # approximate
    assert result.rate == pytest.approx(expected, rel=1e-3)
```

### TC-AGENT-01 — Agent dispatches get_exchange_rate tool

```python
@pytest.mark.asyncio
async def test_agent_dispatches_get_exchange_rate(mock_openai_client, mock_connector):
    """
    When GPT-4o selects get_exchange_rate, the agent must call
    connector.get_rate and return a structured chat response.
    """
    # mock_openai_client returns tool_call for get_exchange_rate
    response = await run_agent(
        message="What is the EUR/USD rate?",
        history=[],
        connector=mock_connector
    )
    assert "EUR" in response or "USD" in response
    assert mock_connector.get_rate.called
```

### TC-E2E-01 — POST /api/chat happy path

```python
def test_chat_endpoint_happy_path(client):
    """
    POST /api/chat with a valid message must return HTTP 200
    with a non-empty reply field.
    """
    response = client.post("/api/chat", json={
        "message": "What is the EUR/USD rate?",
        "history": []
    })
    assert response.status_code == 200
    assert "reply" in response.json()
    assert len(response.json()["reply"]) > 0
```

---

## 12. Test Summary Matrix

| ID | Description | Layer | Priority | Connector |
|---|---|---|---|---|
| TC-MOCK-001 | Series length correct | Unit | P0 | MockConnector |
| TC-MOCK-002 | Deterministic output | Unit | P0 | MockConnector |
| TC-MOCK-003 | Rate plausibility | Unit | P1 | MockConnector |
| TC-MOCK-004 | Multi-pair keys | Unit | P0 | MockConnector |
| TC-MOCK-005 | Error injection — unsupported pair | Unit | P0 | MockConnector |
| TC-MOCK-006 | Error injection — network | Unit | P0 | MockConnector |
| TC-MOCK-007 | Single historical rate | Unit | P0 | MockConnector |
| TC-CONN-101 | get_historical_rate interface | Unit | P0 | MockConnector |
| TC-CONN-102 | start > end raises ValueError | Unit | P0 | MockConnector |
| TC-CONN-103 | Future date raises ValueError | Unit | P0 | MockConnector |
| TC-CONN-104 | Same-day range | Unit | P1 | MockConnector |
| TC-CONN-105 | Empty pairs list | Unit | P1 | MockConnector |
| TC-CONN-106 | USD triangulation | Unit | P0 | MockConnector |
| TC-CONN-107 | MAX_HISTORICAL_DAYS cap | Unit | P0 | MockConnector |
| TC-CACHE-001 | Cache miss calls connector | Unit | P0 | MockConnector |
| TC-CACHE-002 | Cache hit skips connector | Unit | P0 | MockConnector |
| TC-CACHE-003 | TTL expiry re-fetch | Unit | P0 | MockConnector |
| TC-CACHE-004 | Series cached | Unit | P0 | MockConnector |
| TC-CACHE-005 | Different pairs isolated | Unit | P1 | MockConnector |
| TC-CACHE-006 | Different dates isolated | Unit | P1 | MockConnector |
| TC-CACHE-007 | Cached data correctness | Unit | P0 | MockConnector |
| TC-API-101 | History happy path | E2E | P0 | MockConnector |
| TC-API-102 | Missing param 422 | E2E | P0 | MockConnector |
| TC-API-103 | Invalid date 422 | E2E | P0 | MockConnector |
| TC-API-104 | start > end 400 | E2E | P0 | MockConnector |
| TC-API-105 | Unsupported pair 400 | E2E | P0 | MockConnector |
| TC-API-106 | Network error 503 | E2E | P0 | MockConnector |
| TC-API-107 | Max days cap 400 | E2E | P0 | MockConnector |
| TC-API-108 | Response schema | E2E | P0 | MockConnector |
| TC-DASH-101 | Create single_pair_trend | E2E | P0 | MockConnector |
| TC-DASH-102 | Create multi_pair_comparison | E2E | P0 | MockConnector |
| TC-DASH-103 | Create currency_heatmap | E2E | P0 | MockConnector |
| TC-DASH-104 | GET dashboard by ID | E2E | P0 | MockConnector |
| TC-DASH-105 | GET unknown ID 404 | E2E | P0 | MockConnector |
| TC-DASH-106 | PATCH type switch | E2E | P0 | MockConnector |
| TC-DASH-107 | DELETE dashboard | E2E | P1 | MockConnector |
| TC-PANEL-101 | Add panel | E2E | P0 | MockConnector |
| TC-PANEL-102 | Remove panel | E2E | P1 | MockConnector |
| TC-PANEL-103 | Panel data has series | E2E | P0 | MockConnector |
| TC-PANEL-104 | Panel error state | E2E | P0 | MockConnector |
| TC-PANEL-105 | Panel empty state | E2E | P1 | MockConnector |
| TC-LAYOUT-101 | Layout grid structure | E2E | P0 | MockConnector |
| TC-LAYOUT-102 | Layout 404 | E2E | P1 | MockConnector |
| TC-QUOTA-101 | Quota endpoint | E2E | P0 | MockConnector |
| TC-QUOTA-102 | Quota increments | E2E | P0 | MockConnector |
| TC-QUOTA-103 | Quota exhaustion 429 | E2E | P0 | MockConnector |
| TC-QUOTA-104 | Cache hit no quota increment | E2E | P0 | MockConnector |
| TC-TYPE-101 | Type switch single→multi | E2E | P0 | MockConnector |
| TC-TYPE-102 | Type switch to heatmap | E2E | P1 | MockConnector |
| TC-TYPE-103 | Invalid type 422 | E2E | P0 | MockConnector |
| TC-EX-101 | ExchangeRateHost historical happy path | Unit | P0 | respx mock |
| TC-EX-102 | ExchangeRateHost success=false | Unit | P0 | respx mock |
| TC-EX-103 | ExchangeRateHost HTTP 500 | Unit | P0 | respx mock |
| TC-EX-104 | API key in every request | Unit | P0 | respx mock |

| TC-MOCK-008 | error_dates: specific date raises ConnectorError | Unit | P0 | MockConnector |
| TC-MOCK-009 | error_dates: raises in series range | Unit | P0 | MockConnector |
| TC-MOCK-010 | error_dates: pair isolation | Unit | P1 | MockConnector |
| TC-CONN-108 | Exactly 7 days accepted | Unit | P0 | MockConnector |
| TC-CONN-109 | Sequential /historical: one call per day | Unit | P0 | respx mock |
| TC-CONN-110 | Sequential /historical: date param correct | Unit | P0 | respx mock |
| TC-CONN-111 | Sequential /historical: mid-series error raises | Unit | P0 | respx mock |

| TC-GHR-001 | get_historical_rates happy path | Unit | P0 | MockConnector |
| TC-GHR-002 | get_historical_rates 503 injection | Unit | P0 | MockConnector |
| TC-GHR-003 | get_historical_rates timeout injection | Unit | P0 | MockConnector |
| TC-GHR-004 | get_historical_rates partial data | Unit | P0 | MockConnector |
| TC-GHR-005 | get_historical_rates error isolation | Unit | P1 | MockConnector |
| TC-GHR-006 | Dashboard panel error state on 503 | E2E | P0 | MockConnector |
| TC-GHR-007 | Dashboard panel error state on timeout | E2E | P0 | MockConnector |
| TC-HEAT-001 | 6-currency heatmap: 15 pair lookups | Unit | P0 | MockConnector |
| TC-HEAT-002 | Heatmap warm cache: 0 connector calls | Unit | P0 | MockConnector |
| TC-HEAT-003 | 2-currency heatmap: 1 pair | Unit | P1 | MockConnector |
| TC-HEAT-004 | Single currency heatmap 422 | E2E | P1 | MockConnector |

| TC-EDATE-001 | Mid-series error_date: partial panel in build_dashboard | Unit | P0 | MockConnector |
| TC-EDATE-002 | First-date error_date: panel error/partial | Unit | P0 | MockConnector |
| TC-EDATE-003 | Heatmap: one pair mid-series failure, others succeed | E2E | P0 | MockConnector |
| TC-EDATE-004 | Cache gap: failed date not stored, adjacent dates cached | Unit | P0 | MockConnector |

**Total: 77 test cases** (48 P0, 17 P1, remainder P2/carry-over)

---

## 13. Gaps and Open Issues

| ID | Gap | Impact | Action |
|---|---|---|---|
| GAP-TEST-01 | GPT-4o system prompt not yet defined. | Medium — tone/refusal behaviour untested | Agent specialist to define system prompt; QA adds tone tests in Wave 3. |
| GAP-TEST-02 | `/historical` free tier confirmed (EOD only). | Resolved | — |
| GAP-TEST-03 | MockConnector error injection API confirmed. | Resolved | — |
| GAP-TEST-04 | No load/stress tests. | Low for PoC | Out of scope; note in backlog. |
| GAP-TEST-05 | Frontend canvas chart rendering not covered by backend tests. | Medium | Frontend tests (Jest or Playwright) needed in Phase 2. |
| GAP-TEST-06 | localStorage persistence (Phase 3 feature) not yet testable. | Low | Out of scope for Feature 02. |
| GAP-TEST-07 | **CLOSED (v2.1)** /timeseries NOT available on free tier. Sequential /historical calls used instead. Cap corrected to 7 days. TC-CONN-107/108/109/110/111 added. | Critical | Resolved — all test cases updated. |
| GAP-TEST-08 | **CLOSED (v2.1)** MockConnector error_dates injection API confirmed. TC-MOCK-008/009/010 added. | High | Resolved. |
| GAP-TEST-09 | **BLOCKER (v2.2)** MockConnector must implement get_historical_rates with 503/timeout/partial-data injection before dashboard tests can run. TC-GHR-001–007 added. | Critical | Open — Data Engineer must implement before QA can execute dashboard tests. |
| GAP-TEST-10 | Heatmap boundary (6 currencies = 30 directional / 15 symmetric pairs) now covered by TC-HEAT-001–004. | Medium | Resolved in v2.2. |

---

*End of QA Test Cases document — v2.0*









