# agent-workflow-guardrails Specification

## Purpose
TBD - created by archiving change agent-workflow-foundation. Update Purpose after archive.
## Requirements
### Requirement: Agent workflows have bounded runtime
The system SHALL enforce a runtime limit for each agent workflow request.

#### Scenario: Workflow completes within runtime limit
- **WHEN** an agent workflow completes before the configured runtime limit
- **THEN** the system returns the workflow result through the chat response

#### Scenario: Workflow exceeds runtime limit
- **WHEN** an agent workflow exceeds the configured runtime limit
- **THEN** the system stops waiting for the workflow result
- **THEN** the system returns a clear timeout error instead of hanging indefinitely

### Requirement: Agent workflows have bounded orchestration steps
The system SHALL limit the number of model/tool orchestration rounds used by an agent workflow request.

#### Scenario: Workflow reaches step limit
- **WHEN** an agent workflow reaches the configured orchestration step limit before producing a final result
- **THEN** the system stops the workflow
- **THEN** the system returns a clear failure response that identifies the request as too complex or incomplete

### Requirement: Workflow mode does not silently fall back
The system SHALL NOT silently fall back to legacy orchestration when the single chat workflow runtime fails.

#### Scenario: Workflow execution fails
- **WHEN** a chat request runs through the single chat workflow runtime
- **AND** the selected workflow fails
- **THEN** the system returns a clear workflow failure response
- **THEN** the system does not silently re-run the same request through legacy orchestration

### Requirement: Partial source failures are represented explicitly
The system SHALL represent recoverable source-level failures inside workflow results instead of failing the whole workflow when useful partial results are available.

#### Scenario: Optional source fails during market briefing
- **WHEN** a market briefing workflow successfully collects required market context
- **AND** an optional source such as news, FRED, or research fails
- **THEN** the workflow result includes the available successful data
- **THEN** the workflow result includes an explicit warning or error entry for the failed source

#### Scenario: Required source fails during market context collection
- **WHEN** a market context collection workflow cannot collect a required source for the requested context
- **THEN** the workflow returns a clear failure response for that required source
- **THEN** the workflow does not present missing required data as successful context

### Requirement: Workflow execution is observable
The system SHALL emit enough structured logs or metrics to diagnose chat workflow execution.

#### Scenario: Workflow completes successfully
- **WHEN** an agent workflow completes successfully
- **THEN** the system records the workflow name and internal units used
- **THEN** the system records workflow latency and completion status

#### Scenario: Workflow fails
- **WHEN** an agent workflow fails
- **THEN** the system records the workflow name, failure category, and completion status

