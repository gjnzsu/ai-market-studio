## ADDED Requirements

### Requirement: Gateway-routed workflow execution is observable
The system SHALL emit enough structured logs or metrics to diagnose workflow execution when AI traffic is routed through Kong Gateway.

#### Scenario: Gateway-routed workflow completes successfully
- **WHEN** an agent workflow completes successfully with gateway-routed AI traffic
- **THEN** the system records workflow name, orchestration mode, gateway route status, latency, and completion status
- **THEN** the system records tool path metadata for gateway-routed and local connector calls

#### Scenario: Gateway-routed workflow fails
- **WHEN** an agent workflow fails with gateway-routed AI traffic
- **THEN** the system records workflow name, failure category, gateway route status, and completion status
- **THEN** the failure is distinguishable from local connector failures

### Requirement: Gateway failures do not trigger legacy fallback
The system SHALL NOT fall back to legacy orchestration when gateway-routed workflow execution fails.

#### Scenario: Gateway failure during workflow request
- **WHEN** Kong or ai-gateway-service fails during a workflow chat request
- **THEN** the system returns a clear workflow or gateway failure response
- **THEN** the system does not silently re-run the request through legacy orchestration

