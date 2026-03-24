# Code Review Checklist — AI Market Studio PoC

> Version: 1.1
> Author: QA Expert (Wave 2)
> Date: 2026-03-25
> Updated: MockConnector error injection API confirmed (data-engineer); historical endpoint confirmed available on free tier.
> Scope: Backend Python codebase — FastAPI, AI Agent, Data Connector layers

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
| S-05 | P1 | `OPENAI_API_KEY` is handled with the same discipline as above. |
| S-06 | P1 | `Settings` model (pydantic-settings) marks secret fields with `SecretStr` or equivalent — they do not appear in `repr()` or `model_dump()` output by default. |

### 1.2 CORS Policy

| # | Priority | Check |
|---|---|---|
| S-07 | P0 | CORS middleware is configured. `allow_origins` is not `["*"]` in any environment other than local development. |
| S-08 | P1 | If `allow_origins=["*"]` is used for PoC convenience, a TODO comment documents this as a known shortcut to fix before deployment. |
| S-09 | P1 | `allow_credentials=True` is NOT combined with `allow_origins=["*"]` (browsers reject this combination). |
| S-10 | P1 | `allow_methods` and `allow_headers` are as restrictive as the UI requires — not blanket `["*"]` unless justified. |
### 1.3 Input Validation

| # | Priority | Check |
|---|---|---|
| S-11 | P0 | All user-supplied input (chat message, session_id) is validated by Pydantic before reaching the agent or connector layer. |
| S-12 | P0 | Empty string message is rejected at the schema level (not silently passed to GPT-4o). |
| S-13 | P1 | Message length is bounded — an unbounded string could exhaust GPT-4o context or inflate costs. A max length validator (e.g. 2000 chars) is recommended. |
| S-14 | P1 | Currency code inputs to the connector are validated as 3-letter uppercase strings before the HTTP call is made. |
| S-15 | P2 | No user input is interpolated into log messages using `%s` string formatting in a way that could cause log injection. Use structured logging. |

---

## 2. Error Handling

### 2.1 Connector Layer

| # | Priority | Check |
|---|---|---|
| E-01 | P0 | All `httpx` exceptions (`TimeoutException`, `HTTPStatusError`, `RequestError`) are caught and re-raised as `ConnectorError` or a subclass — never propagated raw. |
| E-02 | P0 | `success: false` responses from exchangerate.host are detected and raise `ConnectorError`, not silently return `None` or `0.0`. |
| E-03 | P0 | Empty `quotes` dict (unsupported pair) raises `UnsupportedPairError`, not `KeyError`. |
| E-04 | P0 | Missing API key is detected at construction time and raises `ConnectorError` or `ValueError` before any HTTP call. |
| E-05 | P1 | No bare `except:` or `except Exception:` blocks that swallow errors silently. All catch blocks either re-raise or log and re-raise. |
| E-06 | P1 | Triangulation failure (second HTTP call fails after first succeeds) raises `ConnectorError`, not a partial result. |

### 2.2 Agent Layer

| # | Priority | Check |
|---|---|---|
| E-07 | P0 | `ConnectorError` raised during tool dispatch is caught by the agent and returned to GPT-4o as a tool result error message — not propagated to the API layer as an unhandled exception. |
| E-08 | P0 | Unknown tool name in `dispatch_tool` raises `AgentError`, not `KeyError`. |
| E-09 | P1 | The agent function-calling loop has a maximum iteration guard (e.g. `max_turns=5`) to prevent unbounded loops. |
| E-10 | P1 | OpenAI API errors (`openai.APIError`, `RateLimitError`) are caught and raise `AgentError` with a user-friendly message. |

### 2.3 API Layer

| # | Priority | Check |
|---|---|---|
| E-11 | P0 | `AgentError` is mapped to HTTP 503 with a JSON `{"detail": "..."}` body — not a 500 with a raw traceback. |
| E-12 | P0 | Pydantic `ValidationError` on request parsing is mapped to HTTP 422 (FastAPI default — verify it is not overridden). |
| E-13 | P1 | All exception handlers return JSON-serialisable bodies — not plain text strings. |
| E-14 | P1 | Internal error details (stack traces, API keys in exception messages) are NOT included in HTTP error responses. |
---

## 3. Code Quality

### 3.1 Async Correctness

| # | Priority | Check |
|---|---|---|
| Q-01 | P0 | All I/O-bound operations (HTTP calls, OpenAI SDK calls) use `async`/`await` — no synchronous blocking calls inside `async def` functions. |
| Q-02 | P0 | `httpx.AsyncClient` is used, not `httpx.Client` (synchronous). |
| Q-03 | P0 | `openai.AsyncOpenAI` is used, not `openai.OpenAI` (synchronous). |
| Q-04 | P1 | `AsyncClient` is created once (at app startup or connector construction) and reused — not created per-request, which would exhaust connection pool. |
| Q-05 | P1 | No `time.sleep()` in async context — use `asyncio.sleep()` if waiting is genuinely required. |
| Q-06 | P1 | FastAPI route functions are declared `async def`, not `def`. |

### 3.2 Dependency Injection

| # | Priority | Check |
|---|---|---|
| Q-07 | P0 | `FXAgent` accepts `openai_client` and `connector` as constructor parameters — it does not instantiate them internally. |
| Q-08 | P0 | The API router receives the connector via FastAPI `Depends()` or app state — not a module-level global. |
| Q-09 | P1 | `USE_MOCK_CONNECTOR` env var switches the connector at startup without code changes. |

### 3.3 Layering and Coupling

| # | Priority | Check |
|---|---|---|
| Q-10 | P0 | The agent layer imports only `MarketDataConnector` (ABC) — never `ExchangeRateHostConnector` directly. |
| Q-11 | P0 | The API layer does not import connector or agent implementation classes directly — only interfaces and factory functions. |
| Q-12 | P1 | `ConnectorError` is defined in `connectors/base.py` or `core/errors.py` — not in the concrete connector implementation file. |
| Q-13 | P1 | Return types from `get_exchange_rate` are plain `dict` (per data design) — not Pydantic models or connector-specific dataclasses. |

### 3.4 Configuration

| # | Priority | Check |
|---|---|---|
| Q-14 | P0 | All configuration is loaded via `pydantic-settings` `Settings` class — no bare `os.environ[]` or `os.getenv()` scattered through the codebase. |
| Q-15 | P1 | `Settings` is instantiated once and injected — not re-read on every request. |
| Q-16 | P1 | `.env.example` documents every required env var with a description and example value. |

### 3.5 General Quality

| # | Priority | Check |
|---|---|---|
| Q-17 | P1 | No `print()` statements in production code — use `logging`. |
| Q-18 | P1 | Log levels are appropriate: DEBUG for verbose traces, INFO for request lifecycle, WARNING for recoverable errors, ERROR for unhandled exceptions. |
| Q-19 | P1 | No unused imports or dead code left in merged files. |
| Q-20 | P2 | Type hints are present on all public function signatures in `app/`. |
| Q-21 | P2 | `requirements.txt` pins major and minor versions (e.g. `fastapi>=0.110.0`) — not unpinned (`fastapi`). |

---

## 4. Testing

### 4.1 Coverage of Critical Paths

| # | Priority | Check |
|---|---|---|
| T-01 | P0 | Unit tests exist for `ExchangeRateHostConnector`: happy path, API error, unsupported pair, timeout, missing API key, cross-rate triangulation. |
| T-02 | P0 | Unit tests exist for `MockConnector`: correct schema returned, error pair injection. |
| T-03 | P0 | Unit tests exist for tool dispatch: correct routing, unknown tool raises `AgentError`. |
| T-04 | P0 | Unit tests exist for `ChatRequest`/`ChatResponse` schema validation: valid input, empty message, missing fields. |
| T-05 | P0 | Agent tests mock the OpenAI client — no live LLM calls in CI. |
| T-06 | P0 | E2E tests use `MockConnector` injected via `create_app()` — no live API calls in CI. |
| T-07 | P0 | `EXCHANGERATE_HOST_API_KEY` is set to a dummy value in test config — tests do not depend on a real key being present. |

### 4.2 Test Quality

| # | Priority | Check |
|---|---|---|
| T-08 | P1 | Each test has a single, clear assertion focus — not testing multiple unrelated behaviours in one test function. |
| T-09 | P1 | `respx_mock` (or equivalent) is used to assert that HTTP calls are made with the correct URL, params, and method — not just that no exception is raised. |
| T-10 | P1 | Fixtures are scoped appropriately: `scope="session"` only for truly immutable shared state. |
| T-11 | P1 | No `pytest.mark.skip` without a linked issue or TODO explaining when it will be unskipped. |
| T-12 | P2 | Coverage report is generated in CI (`pytest --cov=backend/app --cov-fail-under=90`). |
| T-13 | P2 | Agent tests use recorded fixtures (not `MagicMock` return values constructed ad-hoc per test) for the most complex flows. |

---

## 5. Cross-Cutting Findings from Wave 1

The following issues were identified by upstream specialists and must be verified in code review:

| ID | Finding | Source | Check |
|---|---|---|---|
| XC-01 | exchangerate.host requires an API key — team_context.md stated "no API key required" which is incorrect. | Data Engineer (Wave 1) | Verify connector reads `EXCHANGERATE_HOST_API_KEY` from env and raises on missing. See S-01, E-04. |
| XC-02 | Non-USD cross-rates require 2 sequential HTTP calls (triangulation). | Data Engineer (Wave 1) | Verify connector implements triangulation. Test TC-CONN-06 must pass. |
| XC-03 | Free tier quota is ~100 req/month — automated tests must never hit live API. | Data Engineer (Wave 1) | Verify `USE_MOCK_CONNECTOR=true` in all CI configs. See T-06, T-07. |
| XC-04 | GPT-4o system prompt is not yet defined. | Architecture Design (Wave 1) | Agent tests must inject a placeholder. Document as GAP-TEST-01. Do not block merge on this. |

---

## 6. Pre-Merge Gate Summary

A PR is ready to merge when:

- [ ] All P0 checklist items pass.
- [ ] `pytest` exits 0 with no skipped P0 tests.
- [ ] Coverage >= 90% on `backend/app/`.
- [ ] No secrets committed (run `git grep -i 'api_key\s*=' -- '*.py'` to verify).
- [ ] `.env` is in `.gitignore`.
- [ ] Reviewer has run `pytest -x` locally and confirmed green.

---

*End of code review checklist.*

