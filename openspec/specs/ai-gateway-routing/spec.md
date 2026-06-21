# ai-gateway-routing Specification

## Purpose
Define how AI Market Studio routes OpenAI-compatible chat completion traffic through the configured AI gateway path while preserving rollback, observability, and API response compatibility.

## Requirements
### Requirement: AI chat completions route through Kong Gateway
The system SHALL route AI chat completion requests from AI Market Studio through Kong Gateway to ai-gateway-service when gateway mode is configured.

#### Scenario: Chat completion uses Kong base URL
- **WHEN** AI Market Studio creates the AI chat completion client in a deployed gateway environment
- **THEN** the client uses the configured Kong Gateway Kubernetes Service OpenAI-compatible base URL
- **THEN** chat completion requests are sent to Kong before ai-gateway-service

#### Scenario: Chat completion does not bypass Kong in GKE
- **WHEN** AI Market Studio is deployed in gateway-routed mode on GKE
- **THEN** the configured AI base URL points to the Kong Gateway service DNS
- **THEN** the configured AI base URL does not point directly to the ai-gateway-service service DNS

#### Scenario: Local development can use a configurable base URL
- **WHEN** AI Market Studio runs in local development
- **THEN** the AI chat completion base URL is configurable without code changes
- **THEN** the configured value may point to Kong, ai-gateway-service directly, or a test double

### Requirement: Gateway request contract is explicit
The system SHALL define the required gateway request contract for AI chat traffic, including route path, authentication, headers, timeout behavior, and error mapping.

#### Scenario: Gateway headers are propagated
- **WHEN** AI Market Studio sends an AI chat completion request through Kong
- **THEN** the request includes the configured authentication material required by the gateway route
- **THEN** request correlation metadata is preserved or generated for downstream observability

#### Scenario: Gateway timeout is mapped clearly
- **WHEN** Kong or ai-gateway-service times out while processing an AI chat completion request
- **THEN** AI Market Studio returns a clear timeout response to the chat API caller
- **THEN** logs identify the failure as gateway-routed AI traffic

#### Scenario: Gateway upstream error is mapped clearly
- **WHEN** Kong returns an upstream, authentication, or route error
- **THEN** AI Market Studio returns a clear service failure response
- **THEN** logs include enough structured metadata to distinguish gateway errors from local connector errors

### Requirement: Gateway routing supports configuration rollback
The system SHALL allow operators to roll AI chat completion traffic back to a previous OpenAI-compatible upstream by configuration.

#### Scenario: Operator changes AI base URL for rollback
- **WHEN** an operator changes the AI base URL away from Kong to a previous OpenAI-compatible upstream
- **THEN** AI Market Studio uses the new configured upstream without code changes
- **THEN** workflow orchestration remains the only supported chat agent path

### Requirement: Chat response shape remains stable
The system SHALL preserve the existing `/api/chat` response shape while routing AI traffic through Kong.

#### Scenario: Gateway-routed workflow response
- **WHEN** a workflow chat request completes through gateway-routed AI traffic
- **THEN** the API response includes `reply`
- **THEN** the API response includes `data`
- **THEN** the API response includes `tool_used`
