## ADDED Requirements

### Requirement: Financial playbook outputs remain stable under gateway routing
The system SHALL preserve financial analysis playbook response shape and semantics when workflow AI traffic is routed through Kong Gateway.

#### Scenario: Gateway-routed playbook briefing
- **WHEN** a workflow market briefing uses a financial analysis playbook
- **AND** AI chat completion traffic is routed through Kong Gateway
- **THEN** the workflow result includes the selected playbook identifier and display name
- **THEN** the workflow result includes source grounding and data gap information
- **THEN** the workflow result remains research-oriented

#### Scenario: Gateway-routed FX carry playbook
- **WHEN** a workflow market briefing uses the FX carry playbook
- **AND** AI chat completion traffic is routed through Kong Gateway
- **THEN** the workflow result includes synthetic forward curve data
- **THEN** the workflow result includes synthetic implied volatility data
- **THEN** the workflow result includes carry metrics derived from the available context and synthetic specialist data
- **THEN** the workflow result identifies synthetic inputs as synthetic rather than live market quotes

