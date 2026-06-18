## 1. Gateway Guardrail Runtime in ai-gateway-service

- [x] 1.1 Add request-side PII masking tests in `ai-gateway-service` for configured categories such as email, phone, and API-like secrets.
- [x] 1.2 Implement request-side PII masking before LiteLLM/provider calls in `ai-gateway-service`.
- [x] 1.3 Add prompt input safety policy tests for allow, audit-only, and blocking decisions.
- [x] 1.4 Implement prompt input safety policy enforcement before provider calls.
- [x] 1.5 Add response safety policy tests for masking PII and blocking unsafe output.
- [x] 1.6 Implement response safety policy enforcement before returning responses to Kong.
- [x] 1.7 Add structured guardrail observability without logging raw sensitive values.
- [x] 1.8 Add feature flags for disabled, audit-only, mask, and enforce modes.

## 2. AI Market Studio Gateway Error Contract

- [x] 2.1 Add tests proving prompt safety denial from the OpenAI-compatible gateway path maps to a clear `/api/chat` error.
- [x] 2.2 Add tests proving response safety denial from the gateway path does not return unsafe model content to the frontend.
- [x] 2.3 Update chat API error mapping for gateway safety denial status codes and machine-readable safety errors.
- [x] 2.4 Ensure gateway safety failures continue to log `ai_path=gateway` and do not trigger legacy fallback behavior.

## 3. Documentation and Deployment

- [x] 3.1 Update `docs/ai-gateway-to-kong-capability-matrix.md` to mark PII masking as implemented in `ai-gateway-service` first, not Kong OSS.
- [x] 3.2 Update `docs/deployments/kong-gateway-integration.md` with guardrail modes, expected error categories, and rollback steps.
- [x] 3.3 Update `docs/gateway-tool-traffic-boundaries.md` to distinguish gateway-routed LLM traffic, ai-gateway-service guardrails, and local connector traffic.
- [x] 3.4 Document the expected `ai-gateway-service` environment variables for guardrail enablement.

## 4. Validation

- [x] 4.1 Run OpenSpec validation for `add-ai-gateway-guardrails`.
- [x] 4.2 Run targeted AI Market Studio chat API and gateway integration tests.
- [x] 4.3 Run the relevant `ai-gateway-service` guardrail test suite after implementing the runtime there.
