## Why

AI Market Studio now routes model traffic through Kong OSS to `ai-gateway-service`, but the AI gateway path does not yet define a first-class safety boundary for sensitive user input or unsafe model output. Since Kong OSS does not provide free built-in AI PII sanitization, the immediate guardrail layer should live in `ai-gateway-service` while remaining observable and contract-driven from AI Market Studio.

## What Changes

- Add an AI gateway guardrail contract for request-side PII masking before provider calls.
- Add prompt input safety policy behavior for blocking or rejecting unsafe prompts before they reach model providers.
- Add response safety policy behavior for masking, blocking, or replacing unsafe model output before it reaches AI Market Studio.
- Document that the first implementation target is `ai-gateway-service`, not Kong OSS Enterprise plugins.
- Update AI Market Studio gateway integration expectations so guardrail failures surface as clear gateway/safety errors instead of generic runtime failures.
- Preserve the existing OpenAI-compatible `/v1/chat/completions` contract for successful requests.

## Capabilities

### New Capabilities

- `ai-gateway-guardrails`: Defines request PII masking, prompt input safety policy, response safety policy, observability, and OpenAI-compatible behavior for the AI gateway path.

### Modified Capabilities

- `agent-workflow-guardrails`: Clarifies how AI Market Studio handles gateway safety failures during workflow chat execution.

## Impact

- Affected runtime boundary: `Backend -> Kong OSS -> ai-gateway-service -> model provider`.
- Affected external service: `ai-gateway-service` must implement the actual PII masking and safety policy layer.
- Affected AI Market Studio code: chat error mapping, gateway integration tests, and deployment/operator documentation.
- Affected configuration: new documented gateway guardrail environment variables or response headers may be consumed by AI Market Studio once exposed by `ai-gateway-service`.
- No breaking change to frontend request/response shape for successful `/api/chat` calls.
