## Context

AI Market Studio currently sends workflow chat completions through the configured OpenAI-compatible path, which can point to Kong Gateway and the self-built ai-gateway-service. The backend already initializes the AI SRE observability SDK and records aggregated prompt/completion tokens for each agent conversation. ai-gateway-service also emits technical LLM metrics into the observability service.

The missing MVP capability is business attribution. Current metrics can explain service/model/provider usage, but they do not reliably distinguish FX data query result generation, advisory report generation, and conversational dashboard generation, nor do they attach project/team/session/request correlation dimensions.

## Goals / Non-Goals

**Goals:**
- Preserve the existing `/api/chat` response contract.
- Add an optional request attribution object to `/api/chat` so clients can provide project/team/user/session/conversation context.
- Generate a stable `requestId` when the client does not provide one.
- Propagate `X-Request-ID`, `X-Consumer-Service`, and low-cardinality business headers to the AI Gateway path.
- Classify the completed workflow into the MVP use cases and features using explicit client context when present, with a backend fallback based on tool/result type and message intent.
- Emit a companion business metric through the existing observability SDK path so Prometheus/Grafana can aggregate cost attribution dimensions.
- Keep token and cost calculation in the existing technical LLM metric path to avoid double-counting.

**Non-Goals:**
- Implement chargeback, budget enforcement, hard quota, approval flows, or automatic model routing.
- Replace ai-gateway-service, Kong Gateway, Prometheus, Grafana, or the AI SRE observability service.
- Add high-cardinality Prometheus labels such as raw user IDs, raw prompts, conversation text, or currency-pair values.
- Change `/api/chat` response shape or require existing clients to send attribution fields.
- Attribute non-LLM `/api/dashboard` data fetch cost in this MVP.

## Decisions

1. **Use optional `client_context` on `/api/chat` rather than a new endpoint.**

   Existing UI and API clients already use `/api/chat` for all three MVP AI entry points. Extending the request model with an optional nested object keeps backward compatibility and keeps attribution close to the originating user action.

   Alternative considered: infer everything from prompts and tool results. This is useful as a fallback, but it is not enough for project/team ownership or user/session correlation.

2. **Emit a companion business metric rather than altering the core LLM token metric first.**

   The existing `llm_call` metric already carries tokens, duration, provider, model, status, and cost calculation. The MVP should add a low-cardinality `business_metric` with labels such as `application`, `project`, `team`, `use_case`, `feature`, `model`, `status`, and `tool_used`. Grafana can then correlate it with the LLM metric by service/model/time window and request logs can correlate exact requests by `requestId`.

   Alternative considered: add all business labels directly to `llm_tokens_total` and `llm_token_cost_usd_total`. That gives simpler PromQL but risks label cardinality and requires broader observability service changes.

3. **Keep gateway as the technical source of truth and backend as the business attribution source.**

   Kong and ai-gateway-service see the actual provider call and usage data. The application backend knows the product use case, feature, tool result, and business context. The MVP propagates shared request IDs and low-cardinality headers so the two perspectives can be joined without duplicating token-cost accounting.

   Alternative considered: make ai-gateway-service infer use case from headers only. That would miss workflow result details known only after tool execution.

4. **Use deterministic classification with explicit client override.**

   If `client_context.useCase` and `client_context.feature` are present, the backend preserves them after validation. Otherwise, it maps:
   - `generate_market_briefing` or `data.type=market_briefing` to `fx-advisory-report` / `advisory-report-generation`
   - `data.type=dashboard` or chart/visualization intent to `chat-dashboard-generation` / `dashboard-generation`
   - `collect_market_context` and `analyze_market_context` to `fx-data-query` / `query-result-generation`

   This gives predictable MVP reporting while keeping UI changes small.

## Risks / Trade-offs

- [Risk] Double-counting cost if both backend and gateway metrics are summed as cost sources. → Mitigation: backend emits attribution as a companion business metric, while existing LLM metrics remain the token/cost source.
- [Risk] Prometheus cardinality grows if raw user/session/conversation IDs become labels. → Mitigation: only low-cardinality fields become labels; request/session/conversation IDs remain request context/log metadata, not Prometheus labels.
- [Risk] Frontend-provided use case values may be absent or wrong. → Mitigation: backend performs deterministic fallback classification and keeps the attribution schema optional.
- [Risk] Existing clients omit the new context. → Mitigation: request model remains backward-compatible and backend fills application/project/team defaults.
- [Risk] Gateway and backend request IDs diverge. → Mitigation: backend generates a request ID per chat request and sends it as `X-Request-ID` on the OpenAI-compatible client.

## Migration Plan

1. Add backend attribution models and fallback classification.
2. Propagate request headers from `run_agent()` to the OpenAI-compatible client.
3. Emit the business attribution metric using the existing observability SDK `increment()` API.
4. Update the static UI to send a minimal `client_context` for `ai-market-studio`.
5. Add unit tests for request model compatibility and attribution classification.
6. Add or document Grafana/Prometheus queries for the MVP panels.

Rollback is configuration-safe: existing clients continue to work without `client_context`, and removing dashboard panels does not affect runtime behavior.

## Open Questions

- Whether the final production dashboard should join exact request-level backend and gateway records in a log store rather than Prometheus alone.
- Whether `projectId` and `teamId` should come from authenticated identity/RBAC once authentication exists, instead of the client payload.
