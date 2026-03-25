# Code Review Checklist — AI Market Studio

> Version: 2.2
> Author: QA Expert
> Date: 2026-03-26
> Scope: Feature 02 — FX Rate Trend Dashboard (extends Feature 01 checklist)
> Update v2.1 (2026-03-26): /timeseries NOT available on free tier. Max days cap corrected to 7. Sequential /historical calls required. MockConnector supports error_dates.
> Update v2.2 (2026-03-26): MockConnector must implement get_historical_rates with 503/timeout/partial-data injection (blocker). Heatmap boundary: 6 currencies = 15 symmetric pairs. New required test files added. 90% coverage gate applies per-file.

---

## How to Use This Checklist

Reviewers work through each section in order. Mark each item:
- `[x]` — Pass
- `[ ]` — Fail / needs fix
- `[~]` — Partial / needs discussion
- `[N/A]` — Not applicable to this PR

A PR may not be merged with any `[ ]` item in **P0** rows.

---

## 1. Security

### 1.1 API Key Handling

| # | Priority | Check |
|---|---|---|
| S-01 | P0 | `EXCHANGERATE_HOST_API_KEY` is read from environment variable only — never hardcoded in source. |
| S-02 | P0 | API key does NOT appear in any log output (`logging`, `print`, `uvicorn` access log). |
| S-03 | P0 | API key does NOT appear in exception messages or tracebacks surfaced to the client. |
| S-04 | P0 | `.env` file is listed in `.gitignore`. Only `.env.example` (with placeholder values) is committed. |
| S-05 | P0 | `.env.example` includes `EXCHANGERATE_API_KEY`, `MAX_HISTORICAL_DAYS`, and `QUOTA_LIMIT_PER_SESSION`. |
| S-06 | P1 | `OPENAI_API_KEY` is handled with the same discipline as above. |
| S-07 | P1 | `Settings` model marks secret fields with `SecretStr` — they do not appear in `repr()` or `model_dump()` output. |

### 1.2 CORS Policy

| # | Priority | Check |
|---|---|---|
| S-08 | P0 | CORS middleware is configured. `allow_origins` is not `["*"]` in any environment other than local development. |
| S-09 | P1 | If `allow_origins=["*"]` is used for PoC, a TODO comment documents this as a known shortcut. |
| S-10 | P1 | `allow_credentials=True` is NOT combined with `allow_origins=["*"]`. |

### 1.3 Input Validation

| # | Priority | Check |
|---|---|---|
| S-11 | P0 | All user-supplied inputs (base, quote, start, end, dashboard name, panel config) are validated by Pydantic models before use. |
| S-12 | P0 | Currency codes are validated against the supported list (USD, EUR, GBP, JPY, AUD, CAD, CHF, CNY, HKD, SGD, NZD) before any connector call. |
| S-13 | P0 | Date strings are parsed into `datetime.date` objects by Pydantic — raw strings never passed to connector. |
| S-14 | P0 | Dashboard name length is bounded (e.g. max 200 chars) to prevent oversized payloads. |
| S-15 | P0 | Panel count per dashboard is bounded (e.g. max 10) to prevent quota exhaustion via a single request. |
| S-16 | P1 | `start` and `end` dates are validated server-side (start ≤ end, end ≤ today, range ≤ MAX_HISTORICAL_DAYS). |

---

## 2. Correctness

### 2.1 Connector Methods

| # | Priority | Check |
|---|---|---|
| C-01 | P0 | `get_historical_rate(base, target, date)` returns a `HistoricalRatePoint` with all five fields: `base`, `target`, `rate`, `date`, `source`. |
| C-02 | P0 | `get_historical_series(base, target, start, end)` returns one point per calendar day in `[start, end]` inclusive (no gaps, no duplicates). |
| C-03 | P0 | `get_multi_pair_series(pairs, start, end)` returns a dict keyed by `"BASE/QUOTE"` strings. |
| C-04 | P0 | USD triangulation is applied for non-USD cross-rates in `get_historical_rate` and `get_historical_series`. |
| C-05 | P0 | `MockConnector` generates deterministic series (same inputs → same outputs). |
| C-06 | P0 | `MockConnector` respects `error_pairs`, `network_error_pairs`, `error_dates`, `http_error_pairs`, `timeout_pairs`, and `partial_data_pairs` constructor args. |
| C-06a | P0 | `MockConnector(error_dates=[(base, target, date)])` raises `ConnectorError` only for the specified (pair, date) tuple — other dates and pairs are unaffected. |
| C-06b | P0 | **BLOCKER:** `MockConnector` implements `get_historical_rates(base, quote, start_date, end_date)` — this method is required before any dashboard tests can run. |
| C-06c | P0 | `MockConnector(http_error_pairs=[(base, quote, 503)])` raises `ConnectorNetworkError` with status 503 for that pair. |
| C-06d | P0 | `MockConnector(timeout_pairs=[(base, quote)])` raises `ConnectorNetworkError` or `ConnectorTimeoutError` to simulate upstream timeout. |
| C-06e | P0 | `MockConnector(partial_data_pairs=[(base, quote, N)])` returns exactly N points for any range request on that pair (simulates partial upstream data). |
| C-07 | P0 | `ExchangeRateHostConnector` calls `/historical` endpoint (not `/timeseries` — unavailable on free tier, not `/live`) for historical data. One call per calendar day. |
| C-07a | P0 | `get_historical_series` makes exactly N sequential calls to `/historical` for an N-day range (verified by TC-CONN-109). No batching or `/timeseries` shortcut. |
| C-07b | P0 | Each `/historical` call passes the correct `date` query parameter in `YYYY-MM-DD` format (verified by TC-CONN-110). |
| C-07c | P0 | A failure on any single `/historical` call in a sequential batch raises `ConnectorError` — dates are not silently skipped (verified by TC-CONN-111). |
| C-08 | P1 | Missing data points (weekends/holidays) are filled with prior-day rate, not zero or null. |

### 2.2 Cache

| # | Priority | Check |
|---|---|---|
| C-09 | P0 | `RateCache` cache key includes base, target, date (or start+end for series) — no cross-contamination between pairs or dates. |
| C-10 | P0 | TTL is enforced correctly — stale entries are not served after expiry. |
| C-11 | P0 | A cache hit does NOT increment the quota counter. |
| C-12 | P1 | Cache is not shared across test cases (each test gets a fresh instance). |

### 2.3 Dashboard Logic

| # | Priority | Check |
|---|---|---|
| C-13 | P0 | Dashboard type switch (`PATCH /api/v1/dashboards/{id}`) preserves existing panels. |
| C-14 | P0 | `currency_heatmap` type adds `grid` field to panel responses. |
| C-14a | P0 | Heatmap for N currencies generates exactly N*(N-1)/2 unique pair lookups (symmetric — each pair fetched once, mirrored for the inverse). |
| C-14b | P0 | 6-currency heatmap = 15 unique pair lookups. Verify with TC-HEAT-001. |
| C-14c | P1 | Heatmap rejects fewer than 2 currencies with HTTP 422. |
| C-15 | P0 | Panel error states (unsupported pair, network error, 503, timeout) do not propagate as HTTP 500 — error is captured per-panel with an `error` field. |
| C-16 | P0 | Dashboard ID and panel ID are unique and non-guessable (UUIDs preferred). |
| C-17 | P1 | Layout endpoint (`GET /api/v1/dashboards/{id}/layout`) returns CSS Grid coordinates for every panel. |

### 2.4 Quota Enforcement

| # | Priority | Check |
|---|---|---|
| C-18 | P0 | Quota counter increments by the number of connector calls made (1 per pair per day for non-cached requests). |
| C-19 | P0 | When `QUOTA_LIMIT_PER_SESSION` is reached, subsequent requests return HTTP 429 — no connector calls are made. |
| C-20 | P0 | `GET /api/v1/quota` returns `used`, `limit`, and `remaining` fields; `remaining == limit - used`. |

---

## 3. Error Handling

| # | Priority | Check |
|---|---|---|
| E-01 | P0 | `UnsupportedPairError` from connector maps to HTTP 400 with a descriptive `detail` message (not a 500). |
| E-02 | P0 | `ConnectorNetworkError` from connector maps to HTTP 503 (not a 500). |
| E-03 | P0 | `ValueError` from date validation maps to HTTP 400 (not a 422 or 500). |
| E-04 | P0 | Missing `EXCHANGERATE_API_KEY` at startup raises a clear configuration error — server does not start silently without it. |
| E-05 | P0 | HTTP 404 is returned for unknown dashboard IDs and panel IDs — not a 500 or empty 200. |
| E-06 | P0 | HTTP 429 is returned when quota is exhausted — response body includes `retry_after` or a quota message. |
| E-07 | P1 | All exception handlers log the error server-side (with stack trace) but return only safe error messages to the client. |
| E-08 | P1 | Dashboard creation with a mix of valid and invalid panels does not fail atomically — valid panels succeed, invalid panels carry per-panel error state. |

---

## 4. Performance & Quota Protection

| # | Priority | Check |
|---|---|---|
| P-01 | P0 | `RateCache` is injected into the connector layer — not bypassed anywhere in the dashboard build path. |
| P-02 | P0 | A single dashboard request for N pairs over D days results in at most N×D connector calls (cache misses only). |
| P-03 | P0 | `MAX_HISTORICAL_DAYS` env var is read from config and enforced in the API layer before any connector call. |
| P-04 | P0 | `QUOTA_LIMIT_PER_SESSION` env var is enforced — requests beyond the limit are rejected before connector call. |
| P-05 | P1 | Multi-pair series requests do not make redundant calls for the same (pair, date) tuple. |
| P-06 | P1 | Cache TTL is configurable via env var — not hardcoded. |
| P-07 | P2 | For multi-pair requests, connector calls are parallelised with `asyncio.gather` where possible. |

---

## 5. Testing

| # | Priority | Check |
|---|---|---|
| T-01 | P0 | All new code has corresponding test stubs in `tests/` directory. |
| T-02 | P0 | `pytest` exits 0 with `USE_MOCK_CONNECTOR=true` — no live API calls in any test. |
| T-03 | P0 | Coverage ≥ 90% on `backend/` globally (verified via `pytest --cov=backend --cov-report=term`). |
| T-03a | P0 | Coverage ≥ 90% on `backend/connectors/cache.py` individually — measured separately. |
| T-03b | P0 | Coverage ≥ 90% on `backend/dashboard.py` individually — measured separately. |
| T-04 | P0 | All P0 test cases from `qa_test_cases.md` v2.2 are implemented (not just stubbed). |
| T-04a | P0 | **BLOCKER:** TC-GHR-001–007 (get_historical_rates injection) cannot be implemented until MockConnector exposes the method. Verify MockConnector is updated before merging dashboard code. |
| T-05 | P0 | `MockConnector` is used in all E2E tests — `ExchangeRateHostConnector` only in unit tests behind `respx.mock`. |
| T-06 | P0 | No test directly instantiates `ExchangeRateHostConnector` without a `respx_mock` fixture active. |
| T-07 | P0 | `USE_MOCK_CONNECTOR=true` is set in all CI/CD pipeline configs (GitHub Actions, etc.). |
| T-08 | P0 | Three new test files exist: `tests/unit/test_cache.py`, `tests/unit/test_dashboard_service.py`, `tests/e2e/test_dashboard_api.py`. |
| T-09 | P1 | Each test function is independent — no shared mutable state between tests. |
| T-10 | P1 | Test fixtures for `client`, `client_with_error_connector`, `client_with_network_error_connector`, and `client_with_timeout_connector` are in `conftest.py`. |
| T-11 | P1 | Agent tests use recorded OpenAI fixtures — no live LLM calls. |

---

## 6. Code Quality & Maintainability

| # | Priority | Check |
|---|---|---|
| Q-01 | P0 | Abstract base class `MarketDataConnector` declares `get_historical_rate`, `get_historical_series`, and `get_multi_pair_series` as `@abstractmethod`. |
| Q-02 | P0 | `HistoricalRatePoint` and `HistoricalRateSeries` are defined as `@dataclass` or Pydantic models — no plain dicts in the connector interface. |
| Q-03 | P0 | Dashboard and panel models are Pydantic models with field-level validation. |
| Q-04 | P1 | `RateCache` is a separate class in `connectors/cache.py` — not inlined into connector or router. |
| Q-05 | P1 | Dashboard type enum (`single_pair_trend`, `multi_pair_comparison`, `currency_heatmap`) is defined as a Python `Enum` — not raw strings. |
| Q-06 | P1 | Chart type enum (`line`, `bar`, `heatmap`, `stats`) is defined as a Python `Enum`. |
| Q-07 | P1 | No magic numbers — `MAX_HISTORICAL_DAYS` default (31), `QUOTA_LIMIT_PER_SESSION` default, cache TTL default are all named constants or config values. |
| Q-08 | P2 | No dead code — removed Feature 01 stubs not referenced by Feature 02 are deleted, not commented out. |
| Q-09 | P2 | Type hints are present on all new public functions and method signatures. |

---

## 7. API Contract Compliance

| # | Priority | Check |
|---|---|---|
| A-01 | P0 | `GET /api/v1/rates/history` response includes `base`, `quote`, `start`, `end`, `series`, `source` fields. |
| A-02 | P0 | Each `series` point includes `date` (ISO 8601 `YYYY-MM-DD`) and `rate` (float > 0). |
| A-03 | P0 | `POST /api/v1/dashboards` returns HTTP 201 with `dashboard_id` and `panels` list. |
| A-04 | P0 | `GET /api/v1/dashboards/{id}` returns HTTP 404 for unknown IDs. |
| A-05 | P0 | `PATCH /api/v1/dashboards/{id}` returns HTTP 200 with updated dashboard. |
| A-06 | P0 | `DELETE /api/v1/dashboards/{id}` returns HTTP 204 (no body). |
| A-07 | P0 | `GET /api/v1/dashboards/{id}/layout` returns `grid` array with per-panel CSS Grid coordinates. |
| A-08 | P0 | `GET /api/v1/quota` returns `used`, `limit`, `remaining` (integer fields). |
| A-09 | P1 | All error responses follow the FastAPI default `{"detail": "..."}` schema. |
| A-10 | P1 | API versioning prefix `/api/v1/` is consistent across all new endpoints. |

---

## 8. Configuration

| # | Priority | Check |
|---|---|---|
| CFG-01 | P0 | `MAX_HISTORICAL_DAYS` env var is present in `config.py` with a default of **7** (not 31). The /timeseries endpoint is unavailable on the free tier; sequential /historical calls are used, so 7 days is the correct default cap. |
| CFG-02 | P0 | `QUOTA_LIMIT_PER_SESSION` env var is present in `config.py` with a documented default. |
| CFG-03 | P0 | `USE_MOCK_CONNECTOR` env var defaults to `false` in production config, `true` in test/CI config. |
| CFG-04 | P0 | All new env vars are documented in `.env.example` with placeholder values and inline comments. |
| CFG-05 | P1 | `CACHE_TTL_SECONDS` env var is present in `config.py` (or cache TTL is derived from a named constant). |

---

## 9. Cross-Cutting Findings (Carried Forward)

| ID | Finding | Source | Check |
|---|---|---|---|
| XC-01 | exchangerate.host requires an API key. | Data Engineer (Wave 1) | Verify connector reads `EXCHANGERATE_HOST_API_KEY` from env and raises on missing. See S-01, E-04. |
| XC-02 | Non-USD cross-rates require USD triangulation (2 sequential calls). | Data Engineer (Wave 1) | Verify `get_historical_rate` and `get_historical_series` apply triangulation. See C-04, TC-CONN-106. |
| XC-03 | Free tier quota is ~100 req/month — automated tests must never hit live API. | Data Engineer (Wave 1) | Verify `USE_MOCK_CONNECTOR=true` in all CI configs. See T-06, T-07. |
| XC-04 | GPT-4o system prompt is not yet defined. | Architecture Design (Wave 1) | Agent tests must inject a placeholder. Document as GAP-TEST-01. Do not block merge on this. |
| XC-05 | EOD rates only — no intraday data on free tier. | Product Documentation (Feature 02) | Verify docs and error messages do not claim intraday capability. |
| XC-06 | A 30-day, 3-panel dashboard = 90 API calls — approaching free quota in one request. | Data Design (Feature 02) | Verify MAX_HISTORICAL_DAYS and panel count caps are enforced. See P-03, S-15. |
| XC-07 | **CRITICAL:** `/timeseries` endpoint is NOT available on the free tier. Historical queries must use sequential `/historical` calls, one per day. | Architect + Data Engineer (Wave 2) | Verify connector uses `/historical` only. No `/timeseries` calls anywhere. See C-07, C-07a, C-07b, C-07c, TC-CONN-109/110/111. |
| XC-08 | `MAX_HISTORICAL_DAYS` default corrected to **7** (not 31). A 7-day, 3-pair dashboard = 21 calls; 31 days = 93 calls, exhausting the monthly quota in one request. | Architect + Data Engineer (Wave 2) | Verify config.py default is 7. See CFG-01, TC-CONN-107/108, TC-API-107. |
| XC-09 | `MockConnector` must support `error_dates` constructor arg for per-(pair, date) error injection. | Architect (Wave 2) | Verify MockConnector implements error_dates. See C-06a, TC-MOCK-008/009/010. |
| XC-10 | `error_dates` must be used in dashboard-service-level tests: partial series handling in `build_dashboard_response()`, heatmap cell mid-series failure, cache gap population. | Architect (Wave 2) | See TC-EDATE-001–004 in `tests/unit/test_dashboard_service.py`. |
| XC-11 | Failed dates (error_dates injection) must NOT be stored in cache — a cached error would poison subsequent requests after the transient failure clears. | QA Expert (Wave 2) | Verify `cache.py` does not store entries when connector raises. See TC-EDATE-004 and checklist C-10. |

---

## 10. Pre-Merge Gate Summary

A PR is ready to merge when ALL of the following are true:

- [ ] All P0 checklist items above are marked `[x]`.
- [ ] `pytest` exits 0 with `USE_MOCK_CONNECTOR=true` and no skipped P0 tests.
- [ ] Coverage ≥ 90% on `backend/` (`pytest --cov=backend --cov-report=term-missing`).
- [ ] No secrets committed (`git grep -i 'api_key\s*=' -- '*.py'` returns no hits).
- [ ] `.env` is in `.gitignore`.
- [ ] `.env.example` includes all new env vars (`MAX_HISTORICAL_DAYS`, `QUOTA_LIMIT_PER_SESSION`, `CACHE_TTL_SECONDS`).
- [ ] Reviewer has run `pytest -x` locally and confirmed green.
- [ ] All new endpoints return correct HTTP status codes per API contract (Section 7).

---

*End of code review checklist — v2.0*

