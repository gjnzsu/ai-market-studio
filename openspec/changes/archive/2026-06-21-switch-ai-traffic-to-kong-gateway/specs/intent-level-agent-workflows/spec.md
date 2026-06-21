## ADDED Requirements

### Requirement: Workflow behavior is compatible with gateway-routed AI traffic
The system SHALL preserve intent-level workflow behavior when AI chat completions are routed through Kong Gateway.

#### Scenario: Model receives workflow tools through gateway-routed completion
- **WHEN** a chat request runs through workflow orchestration
- **AND** AI chat completion traffic is routed through Kong Gateway
- **THEN** the model receives approved intent-level workflow tools
- **THEN** the workflow result can be returned through the existing chat response contract

#### Scenario: Market briefing through gateway-routed completion
- **WHEN** a customer asks for a market briefing
- **AND** AI chat completion traffic is routed through Kong Gateway
- **THEN** the system uses the market briefing workflow
- **THEN** the model receives one structured workflow result instead of orchestrating internal steps directly

### Requirement: Workflow mode does not depend on legacy fallback
The system SHALL complete or fail workflow requests without falling back to legacy orchestration.

#### Scenario: Workflow tool fails under gateway routing
- **WHEN** a workflow tool fails while AI traffic is gateway-routed
- **THEN** the system returns a workflow failure or partial workflow result according to workflow guardrails
- **THEN** the system does not re-run the request with legacy tools

