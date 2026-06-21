# ai-gateway-guardrails Specification

## Purpose
TBD - created by archiving change add-ai-gateway-guardrails. Update Purpose after archive.
## Requirements
### Requirement: Gateway masks PII before model provider calls
The AI gateway service SHALL detect configured PII categories in chat completion request messages and mask those values before forwarding the request to a model provider.

#### Scenario: Request contains maskable PII
- **WHEN** AI Market Studio sends a chat completion request containing configured PII such as an email address or phone number
- **THEN** the AI gateway service masks the sensitive value before the provider request is sent
- **THEN** the AI gateway service preserves enough non-sensitive prompt context for the model request to remain usable

#### Scenario: Request contains no configured PII
- **WHEN** AI Market Studio sends a chat completion request without configured PII
- **THEN** the AI gateway service forwards the request without changing message content

### Requirement: Gateway applies prompt input safety policy
The AI gateway service SHALL evaluate inbound chat prompts against the configured input safety policy before forwarding the request to a model provider.

#### Scenario: Prompt violates input safety policy
- **WHEN** AI Market Studio sends a chat completion request that violates a blocking input safety rule
- **THEN** the AI gateway service rejects the request before calling the model provider
- **THEN** the response includes a machine-readable safety error code

#### Scenario: Prompt passes input safety policy
- **WHEN** AI Market Studio sends a chat completion request that does not violate the configured input safety policy
- **THEN** the AI gateway service allows the request to proceed to the model provider

### Requirement: Gateway applies response safety policy
The AI gateway service SHALL evaluate model responses against the configured output safety policy before returning content to AI Market Studio.

#### Scenario: Model response violates output safety policy
- **WHEN** a model provider returns content that violates a blocking output safety rule
- **THEN** the AI gateway service does not return the unsafe content to AI Market Studio
- **THEN** the response includes a machine-readable safety error code

#### Scenario: Model response contains maskable PII
- **WHEN** a model provider returns content containing configured maskable PII
- **THEN** the AI gateway service masks the sensitive value before returning the response to AI Market Studio

### Requirement: Gateway preserves OpenAI-compatible success responses
The AI gateway service SHALL preserve the OpenAI-compatible response contract for successful chat completion requests that pass guardrails.

#### Scenario: Guarded request succeeds
- **WHEN** request PII masking and safety policies allow a chat completion request
- **AND** the model provider returns a successful completion
- **THEN** AI Market Studio receives an OpenAI-compatible chat completion response
- **THEN** existing OpenAI SDK parsing continues to work without a custom success wrapper

### Requirement: Gateway guardrails are observable
The AI gateway service SHALL emit structured observability metadata for guardrail decisions without logging raw sensitive values.

#### Scenario: PII is masked
- **WHEN** the AI gateway service masks PII in a request or response
- **THEN** it records the guardrail action and PII category
- **THEN** it does not record the raw sensitive value

#### Scenario: Safety policy blocks content
- **WHEN** the AI gateway service blocks a request or response due to safety policy
- **THEN** it records the guardrail action, policy category, and request correlation ID

### Requirement: Gateway guardrails are configurable
The AI gateway service SHALL allow operators to enable, disable, or run guardrails in audit-only mode by configuration.

#### Scenario: Guardrails run in audit-only mode
- **WHEN** guardrails are configured for audit-only mode
- **THEN** the AI gateway service records guardrail decisions
- **THEN** the AI gateway service does not block or mask content solely because of those audit-only decisions

#### Scenario: Guardrails are disabled
- **WHEN** guardrails are disabled by configuration
- **THEN** the AI gateway service preserves the existing OpenAI-compatible proxy behavior
