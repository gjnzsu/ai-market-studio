## MODIFIED Requirements

### Requirement: Workflow mode does not silently fall back
The system SHALL NOT silently fall back to legacy orchestration when the single chat workflow runtime fails.

#### Scenario: Workflow execution fails
- **WHEN** a chat request runs through the single chat workflow runtime
- **AND** the selected workflow fails
- **THEN** the system returns a clear workflow failure response
- **THEN** the system does not silently re-run the same request through legacy orchestration

### Requirement: Workflow execution is observable
The system SHALL emit enough structured logs or metrics to diagnose chat workflow execution.

#### Scenario: Workflow completes successfully
- **WHEN** an agent workflow completes successfully
- **THEN** the system records the workflow name and internal units used
- **THEN** the system records workflow latency and completion status

#### Scenario: Workflow fails
- **WHEN** an agent workflow fails
- **THEN** the system records the workflow name, failure category, and completion status

## REMOVED Requirements

### Requirement: Legacy mode remains isolated from workflow failures
**Reason**: Legacy chat mode no longer exists, so there is no separate legacy runtime to isolate from workflow failures.
**Migration**: Use the single chat workflow runtime and verify failures do not mutate the approved workflow tool set.
