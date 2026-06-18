# AI Gateway Service to Kong Capability Matrix

Last updated: 2026-06-18

## Purpose

This matrix evaluates which `ai-gateway-service` responsibilities are good candidates to migrate into Kong Gateway, which should stay in `ai-gateway-service`, and which need proof-of-concept validation before a decision.

Current production path:

```text
ai-market-studio backend
  -> Kong Gateway OSS
  -> ai-gateway-service, FastAPI + LiteLLM
  -> OpenAI / DeepSeek
```

The target should not be "move everything into Kong". The safer framing is:

```text
Move cross-cutting gateway policy into Kong.
Keep product-specific or fast-changing AI orchestration in ai-gateway-service until Kong has proven parity.
```

## Current Responsibilities

Based on the current `ai-market-studio` documentation, `ai-gateway-service` owns:

- OpenAI-compatible `/v1/chat/completions` endpoint behind Kong.
- OpenAI and DeepSeek provider key ownership.
- Model routing by model name, including `gpt-5.4`, `gpt-4o`, `gpt-4o-mini`, and `deepseek-chat`.
- Provider abstraction through FastAPI + LiteLLM.
- Centralized LLM gateway boundary for backend traffic.
- Near-term AI guardrails, including PII masking and prompt/response safety policy, because the current Kong OSS deployment does not include Kong AI Gateway Enterprise plugins.

Kong currently owns:

- Internal gateway entrypoint for AI traffic.
- Routing `/v1`, `/health`, and `/readiness` to `ai-gateway-service`.
- Correlation ID generation via `X-Request-ID`.
- Basic request rate limiting.

## Migration Matrix

| Capability | Current Owner | Kong Capability | Migration Fit | Recommendation |
| --- | --- | --- | --- | --- |
| `/v1/chat/completions` OpenAI-compatible proxy | ai-gateway-service / LiteLLM | Kong AI Proxy can accept standardized OpenAI-style requests and translate to provider formats. | Medium | Validate with one non-critical route before replacing LiteLLM. |
| Basic HTTP routing to AI upstream | Kong | Kong already handles this with DB-less config. | High | Keep in Kong. Already migrated. |
| Health and readiness forwarding | Kong -> ai-gateway-service | Kong can route `/health` and `/readiness`. | High | Keep in Kong while ai-gateway-service remains upstream. |
| Correlation ID / request tracing headers | Kong | Kong correlation-id plugin already configured. | High | Keep in Kong. Standardize header contract across services. |
| Basic request rate limiting | Kong | Kong OSS rate-limiting plugin already configured. | High | Keep in Kong. Consider consumer-aware limits when auth exists. |
| Token-aware AI rate limiting | ai-gateway-service or observability layer, if implemented | Kong AI Rate Limiting Advanced can use AI plugin context and token/cost signals, but it is AI Gateway Enterprise. | Medium | Good future migration if Enterprise licensing and metric parity are acceptable. |
| Provider key ownership | ai-gateway-service secrets | Kong AI Proxy can hold provider credentials in plugin config or secrets depending deployment model. | Medium | Migrate only after secret management, rotation, and blast-radius design are clear. |
| Model-name routing, e.g. `gpt-4o-mini` vs `deepseek-chat` | ai-gateway-service / LiteLLM | Kong AI Proxy/AI Proxy Advanced can route to provider/model targets; advanced multi-target routing requires AI Gateway capabilities. | Medium | POC with exact supported provider list and model aliases. Keep fallback to ai-gateway-service during transition. |
| Multi-provider load balancing | ai-gateway-service / LiteLLM, if implemented | Kong AI Proxy Advanced supports multiple providers/models and load balancing. AI Gateway Enterprise capability. | Medium | Candidate for Phase 2, not first migration. |
| Semantic routing by prompt intent | ai-gateway-service, if implemented later | Kong AI Proxy Advanced has semantic routing examples. | Low-Medium | Avoid early migration. Useful only after routing policy is stable and testable. |
| Provider fallback / failover | ai-gateway-service / LiteLLM, if implemented | Kong AI Proxy Advanced supports advanced target behavior, but exact fallback semantics need validation. | Medium | Do not migrate until behavior is proven with provider outage tests. |
| Streaming chat completions | ai-gateway-service / LiteLLM | Kong AI Proxy Advanced changelog notes streaming support; verify for selected providers and SDK behavior. | Medium | POC required before switching production streaming traffic. |
| PII masking / sanitization | ai-gateway-service first | Kong AI PII Sanitizer can protect request and response bodies before upstream/client, but it is an Enterprise AI Gateway capability. | High for need, Low for Kong OSS migration | Implement first in `ai-gateway-service` behind Kong OSS. Revisit Kong migration only with Enterprise licensing. |
| Prompt safety / response safety guardrails | ai-gateway-service first | Kong has AI guard plugins such as AI Lakera Guard and semantic prompt/response guard capabilities, but advanced AI guardrails require licensed capabilities or external services. | Medium | Gateway-layer policy belongs in `ai-gateway-service` for now; keep business-specific financial checks in backend. |
| Semantic cache | ai-gateway-service or none | Kong AI Semantic Cache exists. | Low-Medium | Consider later for repeated low-risk prompts. Avoid caching personalized or PII-bearing prompts. |
| RAG injection | ai-market-studio backend currently calls RAG connector locally | Kong plugin hub lists AI RAG Injector capabilities. | Low | Do not migrate now. Current RAG has product-specific source handling and citations. |
| Cost tracking and token accumulation per user query | ai-market-studio backend + AI SRE Observability | Kong can emit gateway metrics, but current app accumulates tokens across multi-round agent loops. | Low-Medium | Keep current observability until Kong metrics can reproduce query-level cost semantics. |
| Business workflow/tool orchestration | ai-market-studio backend | Kong is not the right layer for app workflows. | Low | Keep in backend. Do not migrate. |
| Market data connectors: FX, news, FRED, RAG | ai-market-studio backend connectors | Not AI gateway responsibilities. | Low | Keep local until a separate connector service strategy exists. |
| Public frontend-to-backend API gateway | Direct backend LoadBalancer today | Kong/Gateway API/Ingress could front `/api/*`. | Separate decision | Do not bundle with AI gateway migration. Treat as public API entry architecture. |

## Recommended Phases

### Phase 0: Keep Current Split

Keep the current production path:

```text
Backend -> Kong OSS -> ai-gateway-service -> Providers
```

Use Kong for routing, correlation IDs, and basic rate limiting. Keep LiteLLM in `ai-gateway-service` as the provider abstraction.

### Phase 1: Gateway Guardrails in ai-gateway-service

Add gateway-level guardrails inside `ai-gateway-service` before replacing the model proxy:

- PII request masking or audit.
- PII response masking or audit.
- Prompt/response safety policy for broad categories.
- Better per-consumer or per-service rate limits.

This gives immediate risk reduction while preserving the existing LiteLLM behavior and avoiding a Kong Enterprise dependency.

### Phase 2: Parallel AI Proxy Route

Create a parallel Kong AI Proxy route for one low-risk model, for example:

```text
/v1-kong-poc/chat/completions -> Kong AI Proxy -> OpenAI
```

Validate:

- Request/response compatibility with `AsyncOpenAI`.
- Tool-calling payload behavior.
- Streaming behavior, if used.
- Error mapping.
- Token usage fields.
- Provider timeout and retry behavior.
- Observability parity.

### Phase 3: Partial Migration

Move the simplest model routes to Kong if Phase 2 passes:

- `gpt-4o-mini`
- `gpt-4o`

Keep `deepseek-chat`, fallback behavior, and any special provider normalization in `ai-gateway-service` until proven.

### Phase 4: Retire or Shrink ai-gateway-service

Only retire `ai-gateway-service` if Kong covers:

- All required providers.
- Model aliasing.
- Provider key rotation.
- Failover/fallback semantics.
- Usage/cost observability.
- Guardrails.
- Rollback.

Otherwise, keep `ai-gateway-service` as a custom adapter behind Kong.

## Decision Summary

Good first migration candidates:

- Guardrails such as PII masking in `ai-gateway-service`.
- More expressive rate limiting.
- Provider-neutral routing for one simple OpenAI model.
- Correlation and audit enrichment.

Keep in `ai-gateway-service` for now:

- LiteLLM provider abstraction.
- DeepSeek route until exact Kong parity is validated.
- Custom fallback/failover behavior.
- Any model alias logic that changes often.

Keep in `ai-market-studio` backend:

- Agent workflow orchestration.
- Tool calling and local connector dispatch.
- Financial product-specific guardrails and response shaping.
- Query-level token/cost aggregation until gateway metrics provide equal semantics.

## References

- Kong AI Proxy: https://developer.konghq.com/plugins/ai-proxy/
- Kong AI Proxy Advanced: https://developer.konghq.com/plugins/ai-proxy-advanced/
- Kong AI Rate Limiting Advanced: https://developer.konghq.com/plugins/ai-rate-limiting-advanced/
- Kong AI PII Sanitizer: https://developer.konghq.com/plugins/ai-sanitizer/
- Kong AI Semantic Cache: https://developer.konghq.com/plugins/ai-semantic-cache/
- Kong plugin compatibility: https://developer.konghq.com/plugins/compatibility/
