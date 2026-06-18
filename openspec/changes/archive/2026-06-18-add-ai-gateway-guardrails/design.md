## Context

AI Market Studio currently sends model-provider traffic through `OPENAI_BASE_URL`, which points to Kong OSS in GKE. Kong forwards `/v1` traffic to `ai-gateway-service`, where FastAPI + LiteLLM owns provider keys and model routing. Kong OSS gives the project routing, correlation IDs, and basic rate limiting, but Kong's AI PII Sanitizer and several AI safety plugins require Kong AI Gateway Enterprise licensing.

The near-term safety layer should therefore be implemented in `ai-gateway-service`, not in Kong OSS. AI Market Studio still needs a clear contract for how that layer behaves because `/api/chat` depends on OpenAI-compatible responses from the gateway path.

## Goals / Non-Goals

**Goals:**

- Define request-side PII masking before prompts reach model providers.
- Define prompt input safety policy behavior for unsafe or disallowed prompts.
- Define response safety policy behavior before model output reaches AI Market Studio.
- Preserve OpenAI-compatible success responses for AI Market Studio.
- Surface guardrail denials and gateway safety failures through clear HTTP errors and structured logs.
- Keep Kong OSS as the routing and basic policy layer while `ai-gateway-service` owns AI-specific guardrails.

**Non-Goals:**

- Do not require Kong Enterprise or Kong AI Gateway licensed plugins.
- Do not migrate LiteLLM provider routing out of `ai-gateway-service`.
- Do not move AI Market Studio workflow/tool orchestration into the gateway.
- Do not move FX, news, FRED, or RAG connector traffic behind Kong as part of this change.
- Do not guarantee perfect PII detection; the first layer is deterministic and testable, with room for stronger detectors later.

## Decisions

### Implement guardrails in `ai-gateway-service`

`ai-gateway-service` should apply guardrails before and after LiteLLM provider calls. Request-side processing runs before sending prompts upstream. Response-side processing runs after receiving model output and before returning to Kong.

Alternative considered: use Kong AI PII Sanitizer. This is deferred because the project currently runs Kong OSS and the official PII sanitizer is an AI Gateway Enterprise capability.

### Keep Kong OSS as the stable entrypoint

Kong remains the service boundary for AI traffic, with `/v1`, `/health`, and `/readiness` forwarding to `ai-gateway-service`. This keeps the existing `OPENAI_BASE_URL` stable for AI Market Studio.

Alternative considered: bypass Kong and call `ai-gateway-service` directly for guardrail testing. This weakens the production traffic path and should be limited to rollback or isolated tests.

### Preserve OpenAI-compatible success responses

When a request passes guardrails, AI Market Studio should receive the same OpenAI-compatible response shape it already expects from `client.chat.completions.create(...)`. Guardrail metadata should be exposed through logs and optional headers, not by changing the successful response body in a way that breaks OpenAI SDK parsing.

Alternative considered: add a custom JSON wrapper around all gateway responses. This would break OpenAI SDK compatibility and force backend changes for the happy path.

### Use explicit safety failures for blocked requests

If prompt input is blocked, `ai-gateway-service` should return an HTTP `4xx` response with a machine-readable error code such as `prompt_safety_violation`. If response output is blocked after the provider call, it should return an HTTP `5xx` or policy-specific error that AI Market Studio maps to a clear AI gateway safety error instead of a generic internal error.

Alternative considered: silently replace unsafe output with a generic answer. That hides the failure category and makes safety behavior hard to audit.

### Start with mask-and-log for PII, block for high-confidence safety violations

Request PII should be masked by default rather than blocked when safe to do so. Prompt/response safety violations should block when the configured policy marks them high confidence.

Alternative considered: block every PII hit. That is safer but likely to break legitimate financial workflows where users paste emails, names, or account references that can be redacted without losing the analytical intent.

## Risks / Trade-offs

- PII false negatives -> Keep the detector isolated and testable so stronger detectors can be added later.
- PII false positives -> Prefer masking over blocking for request PII, and include audit metadata.
- Response blocking after provider cost is incurred -> Accept for the first version; later add prompt-side policy improvements and cheaper pre-checks.
- OpenAI SDK error mapping may collapse custom gateway errors -> Add AI Market Studio tests that map gateway safety status codes to clear `/api/chat` responses.
- Split implementation across repositories -> Keep this OpenSpec change focused on contracts, AI Market Studio integration, and documentation while `ai-gateway-service` implements the guardrail runtime.

## Migration Plan

1. Add the OpenSpec contract in this repository.
2. Implement the guardrail runtime in `ai-gateway-service` behind feature flags.
3. Add AI Market Studio integration tests that simulate guardrail denial responses from the OpenAI-compatible gateway client.
4. Update deployment documentation with the expected guardrail environment variables and rollback steps.
5. Enable request PII masking in audit or mask mode first.
6. Enable prompt/response safety blocking for high-confidence policy violations.

Rollback is configuration-based: disable the guardrail feature flags in `ai-gateway-service` while keeping `OPENAI_BASE_URL` pointed at Kong. If the whole gateway path is unhealthy, rollback remains changing `OPENAI_BASE_URL` to a previous OpenAI-compatible upstream.

## Open Questions

- Which exact PII categories will `ai-gateway-service` implement first: email, phone, API keys, addresses, national IDs, account numbers, or all of these?
- Should low-confidence prompt safety hits be audit-only or blocked in the first production rollout?
- Should response safety failures return `502`, `503`, or a custom `4xx` policy status from `ai-gateway-service`?
