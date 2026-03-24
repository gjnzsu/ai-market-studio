# AI Market Studio — Product Documentation

> Role: Business Analyst
> Last updated: 2026-03-25
> Status: PoC Definition

---

## 1. Product Vision and Goals

**Vision:** AI Market Studio is an AI-powered market data interface that lets financial professionals query live and historical FX rates through natural language — no SQL, no dashboards, no manual lookups.

**PoC Goal:** Demonstrate a clean, layered architecture for an FX market data chatbot. The PoC is scoped to a single data source (exchangerate.host), a single query type (FX spot rates), and a single-page browser UI. It is a handoff-ready reference implementation, not a production system.

**Success Criteria for PoC:**
- A user can open `index.html` in a browser, type a natural-language FX question, and receive a coherent, data-backed answer.
- The architecture is clearly layered: UI → API → Agent → Connector → Data Source.
- All layers are independently testable.
- A new data connector can be added without modifying the agent or API layer.

---

## 2. User Stories

### US-01 — Query Live Exchange Rate
**As a** trader or analyst,
**I want to** ask "What is EUR/USD right now?" in a chat window,
**So that** I can get the current exchange rate without leaving my workflow.

**Acceptance Criteria:**
- AC-01.1: Sending a message containing a recognisable currency pair (e.g. EUR/USD) returns a response with the current rate and the date it was retrieved.
- AC-01.2: The response is in plain English (e.g. "The current EUR/USD rate is 1.0823 as of 2026-03-25.").
- AC-01.3: The rate is sourced live from the data connector, not hardcoded.
- AC-01.4: If the data source is unavailable, the chatbot returns a clear error message rather than a blank or crash.
- AC-01.5: Response appears in the chat window within 10 seconds under normal network conditions.

---

### US-02 — Query Historical Exchange Rate
**As a** analyst,
**I want to** ask "What was GBP/JPY on 1 March 2026?",
**So that** I can look up a past rate for reporting or reconciliation.

**Acceptance Criteria:**
- AC-02.1: A query with a recognisable date returns the rate for that specific date.
- AC-02.2: Dates are accepted in natural language ("1 March 2026", "March 1 2026", "2026-03-01").
- AC-02.3: If the requested date is in the future, the chatbot responds that future rates are unavailable.
- AC-02.4: If the requested date predates available data, the chatbot returns a clear message.

---

### US-03 — List Supported Currencies
**As a** user,
**I want to** ask "What currencies do you support?",
**So that** I know which pairs I can query.

**Acceptance Criteria:**
- AC-03.1: The chatbot returns a list of ISO 4217 currency codes it can query.
- AC-03.2: The list reflects what the data connector actually supports, not a hardcoded list.
- AC-03.3: The response is readable (not a raw JSON dump).

---

### US-04 — Graceful Handling of Unsupported Queries
**As a** user,
**I want to** receive a helpful message when I ask something outside the chatbot's scope,
**So that** I understand what it can and cannot do.

**Acceptance Criteria:**
- AC-04.1: Queries unrelated to FX rates (e.g. "What is the weather?") receive a polite out-of-scope response.
- AC-04.2: Queries for unsupported currency codes return a message naming the unsupported code.
- AC-04.3: The chatbot never returns a raw Python traceback or unhandled exception to the user.

---

### US-05 — Multi-turn Conversation Context
**As a** user,
**I want to** ask follow-up questions (e.g. "What about USD/JPY?") after an initial query,
**So that** I can explore rates without repeating context.

**Acceptance Criteria:**
- AC-05.1: The frontend maintains the full conversation history and sends it with each request.
- AC-05.2: The agent uses prior messages when formulating its response.
- AC-05.3: A follow-up question referencing a previously mentioned currency pair resolves correctly.

---

## 3. API Contract

### Base URL
```
http://localhost:8000
```

---

### POST /api/chat

Send a conversation turn to the AI agent and receive a natural-language reply.

**Request**
```http
POST /api/chat
Content-Type: application/json
```

```json
{
  "messages": [
    { "role": "user",      "content": "What is EUR/USD right now?" },
    { "role": "assistant", "content": "The current EUR/USD rate is 1.0823 as of 2026-03-25." },
    { "role": "user",      "content": "What about GBP/USD?" }
  ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `messages` | array | Yes | Ordered conversation history. Minimum 1 item. Last item must have `role: "user"`. |
| `messages[].role` | string | Yes | One of: `"user"`, `"assistant"`. |
| `messages[].content` | string | Yes | Message text. Non-empty. |

**Response — 200 OK**
```json
{
  "reply": "The current GBP/USD rate is 1.2654 as of 2026-03-25."
}
```

| Field | Type | Description |
|---|---|---|
| `reply` | string | Natural-language response from the AI agent. |

**Response — 422 Unprocessable Entity** (malformed request body)
```json
{
  "detail": [
    {
      "loc": ["body", "messages"],
      "msg": "field required",
      "type": "missing"
    }
  ]
}
```
Standard FastAPI / Pydantic validation error format.

**Response — 500 Internal Server Error** (agent or connector failure)
```json
{
  "detail": "Agent error: upstream data source unavailable."
}
```

| HTTP Status | Trigger |
|---|---|
| 200 | Successful agent response. |
| 422 | Request body fails Pydantic validation (missing fields, wrong types). |
| 500 | OpenAI API key missing/invalid, data connector unreachable, unhandled agent exception. |

---

### GET /health _(optional, recommended)_

Liveness check for the backend.

**Response — 200 OK**
```json
{ "status": "ok" }
```

---

### Pydantic Models (informational)

```python
# backend/models.py

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]   # min_length=1

class ChatResponse(BaseModel):
    reply: str
```

---

## 4. Out-of-Scope for PoC

The following are explicitly deferred. They must NOT be added to the PoC implementation.

| Item | Rationale |
|---|---|
| Authentication / authorisation | No user accounts; PoC runs locally. |
| Session persistence / database | Conversation state lives in the browser only. |
| Rate limiting / throttling | Not needed for single-user local PoC. |
| Charting / data visualisation | UI is text-only chat. |
| Multiple data sources | Only exchangerate.host in PoC; connector abstraction enables future sources. |
| Streaming responses | Single-shot request/response only; no SSE or WebSocket. |
| Deployment / containerisation | No Docker, no cloud deployment for PoC. |
| Production error monitoring | No Sentry, no structured logging pipeline. |
| Equity, commodity, or crypto data | FX rates only. |
| User-configurable model selection | Model is set by `OPENAI_MODEL` env var; no UI control. |
| Internationalisation (i18n) | English only. |

---

## 5. Conversational UX — Example Queries and Responses

These examples define the expected chatbot behaviour and serve as a reference for agent prompt design and E2E tests.

| User Query | Expected Chatbot Response (illustrative) |
|---|---|
| "What is EUR/USD right now?" | "The current EUR/USD exchange rate is 1.0823 as of 2026-03-25." |
| "What was GBP/JPY on 1 March 2026?" | "On 1 March 2026, the GBP/JPY exchange rate was 191.42." |
| "How many dollars is 100 euros?" | "Based on the current EUR/USD rate of 1.0823, 100 EUR is approximately 108.23 USD." |
| "What currencies do you support?" | "I can query exchange rates for the following currencies: AUD, CAD, CHF, EUR, GBP, JPY, USD, and many more. Here is the full list: [list]." |
| "What is USD/USD?" | "EUR/USD is 1.0000 — a currency always equals itself. Did you mean a different pair?" |
| "What is BANANA/USD?" | "BANANA is not a recognised currency code. Please use a standard ISO 4217 code such as EUR, GBP, or JPY." |
| "What will EUR/USD be next week?" | "I can only provide current and historical exchange rates, not forecasts." |
| "What is the weather in London?" | "I'm a foreign exchange rate assistant and can only help with FX queries. Try asking me about a currency pair!" |
| "What about USD/JPY?" _(follow-up)_ | "The current USD/JPY exchange rate is 151.23 as of 2026-03-25." |
| "Show me a chart" | "Chart visualisation is not available in this version. I can give you the rate as a number." |

### Tone and Style Guidelines
- Responses are concise and factual.
- Always include the rate value and the date it was retrieved.
- Never expose internal tool names, JSON payloads, or stack traces.
- Out-of-scope requests receive a brief, helpful redirect.

---

## 6. Functional Requirements

| ID | Requirement |
|---|---|
| FR-01 | The system shall accept a conversation history (array of user/assistant messages) via POST /api/chat. |
| FR-02 | The system shall extract currency pair and optional date from the user's message using GPT-4o function calling. |
| FR-03 | The system shall retrieve a live exchange rate when no date is specified. |
| FR-04 | The system shall retrieve a historical exchange rate when a specific date is provided. |
| FR-05 | The system shall return the list of supported currencies on request. |
| FR-06 | The system shall return a natural-language reply synthesised by GPT-4o. |
| FR-07 | The system shall return a user-friendly error message if the data source is unavailable. |
| FR-08 | The system shall return a user-friendly error message for unrecognised currency codes. |
| FR-09 | The system shall handle multi-turn conversations by passing the full message history to the agent. |
| FR-10 | The frontend shall maintain conversation history in browser memory (JS array) across turns. |
| FR-11 | The frontend shall display both user and assistant messages in a scrollable chat window. |
| FR-12 | The data connector interface shall be abstract, enabling future connectors without modifying the agent. |

---

## 7. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | **Latency:** End-to-end response (UI send → UI render) should be under 10 seconds on a standard broadband connection under normal OpenAI API conditions. |
| NFR-02 | **Reliability:** The backend shall not crash on malformed user input; all errors are caught and returned as structured HTTP responses. |
| NFR-03 | **Testability:** Each layer (connector, agent, API, UI) is independently testable with mocks. |
| NFR-04 | **Extensibility:** Adding a new data connector requires only implementing the abstract base class; no changes to agent or API layers. |
| NFR-05 | **Security:** The OpenAI API key is never exposed to the frontend. It is loaded from environment variables server-side only. |
| NFR-06 | **Portability:** The backend runs on Python 3.11+. The frontend runs in any modern browser with no build step. |
| NFR-07 | **Code Style:** Python code follows PEP 8. Modern type hints are used throughout (`list[str]`, not `List[str]`). |

---

## 8. Product Roadmap

### Phase 1 — PoC (current)
- Single FX data source (exchangerate.host)
- Live and historical spot rate queries
- Plain-text chat UI
- Local execution only
- Unit, agent, and E2E tests

### Phase 2 — Enhanced Data Coverage
- Add second data connector (e.g. Alpha Vantage or Open Exchange Rates) with fallback logic
- Extend agent tools: bid/ask spread, intraday OHLC, rate change % over period
- Support equity and commodity data via additional connector implementations
- Connector registry: agent selects best source per query type

### Phase 3 — Production Readiness
- User authentication (OAuth2 / API keys)
- Session persistence (PostgreSQL or Redis for conversation history)
- Rate limiting and abuse prevention
- Structured logging and error monitoring (e.g. Sentry)
- Docker containerisation and CI/CD pipeline
- Streaming responses (SSE or WebSocket) for perceived latency improvement

### Phase 4 — Rich UX
- Charting integration (e.g. TradingView Lightweight Charts)
- Exportable query results (CSV, PDF)
- Saved watchlists and alert thresholds
- Embeddable widget for third-party integration
- Mobile-responsive UI

---

## 9. Requirement Gaps and Ambiguities

| ID | Gap / Ambiguity | Impact | Recommendation |
|---|---|---|---|
| GAP-01 | ~~exchangerate.host free tier has no API key but has rate limits (undocumented).~~ **UPDATED — see GAP-07:** API key is required; 100 req/month free tier limit confirmed. | Medium | Add HTTP status code handling for 429/401 in connector. Monitor request usage during demo. |
| GAP-02 | **UPDATED:** exchangerate.host free tier locks base currency to USD and requires an `access_key` API key. Cross-pair queries (e.g. EUR/JPY) resolved via single HTTP call using USD as intermediary: `EUR/JPY = USDJPY / USDEUR`. No additional HTTP calls; no latency risk to NFR-01. | Medium | Connector always fetches with `source=USD`; cross-rate computed in Python. `EXCHANGERATE_HOST_API_KEY` is a required credential (see GAP-07). |
| GAP-03 | No maximum message history length is defined. Very long conversations will increase token usage and latency. | Low | Define a practical limit (e.g. last 20 messages) in config. Agent layer should truncate if needed. |
| GAP-04 | The system prompt for the GPT-4o agent is not defined in team context. The agent's tone, refusal behaviour, and tool-calling strategy depend on it. | High | Agent specialist must define and document the system prompt. BA to review for UX consistency with Section 5. |
| GAP-05 | Historical data availability on exchangerate.host free tier is not confirmed. Some free tiers only provide current rates. | Medium | Connector specialist to verify and document actual endpoint capabilities. If historical is unavailable, US-02 must be descoped or the connector must return a clear "not supported" response. |
| GAP-06 | No CORS origin restriction is specified. The PoC opens CORS to all origins (`*`), which is acceptable locally but must be locked down before any deployment. | Low for PoC | Document as a known PoC shortcut. Add to Phase 3 hardening backlog. |
| GAP-07 | `EXCHANGERATE_HOST_API_KEY` is a required credential that was not listed in the original team context. Without it, all connector calls will fail (HTTP 401). | High | Add `EXCHANGERATE_HOST_API_KEY` to `.env` and `config.py` alongside `OPENAI_API_KEY`. Document in setup/prerequisites. Free tier allows 100 req/month — sufficient for PoC demos but operators must monitor usage. |

---

## 10. Cross-Cutting Concerns

- **GAP-02 (cross-rate calculation):** Resolved. Connector fetches `source=USD` in a single call; Python computes cross-rates. No latency risk to NFR-01.
- **GAP-04 (system prompt)** is a shared concern between the Business Analyst (UX/tone) and AI Agent Specialist (tool-calling behaviour). Both must align before agent implementation is complete.
- **GAP-07 (API key):** `EXCHANGERATE_HOST_API_KEY` is a required credential. Backend config, `.env.example`, and setup documentation must list it explicitly.
- **CORS policy** (GAP-06) must be documented in the backend config so the frontend specialist does not hardcode origins.
- **Demo operational constraint:** Free tier cap of 100 req/month means the PoC is suitable for limited demos only. Teams doing extended testing should obtain a paid API key.

---

*End of product documentation.*