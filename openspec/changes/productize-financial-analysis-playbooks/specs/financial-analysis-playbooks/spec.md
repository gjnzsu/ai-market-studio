## ADDED Requirements

### Requirement: Runtime financial analysis playbooks are available
The system SHALL provide runtime financial analysis playbook definitions for workflow-mode market analysis.

#### Scenario: Playbook registry includes initial playbooks
- **WHEN** the system initializes the financial analysis playbook registry
- **THEN** the registry includes playbooks for FX carry, macro-rates monitoring, FX morning notes, and FX/macro catalyst calendars
- **THEN** each playbook includes an identifier, display name, intent triggers, required sources, optional sources, and output sections

### Requirement: Playbooks are selected from request intent
The system SHALL select a financial analysis playbook from explicit request parameters or inferred user intent.

#### Scenario: Explicit playbook is requested
- **WHEN** a workflow market briefing request includes a supported playbook identifier
- **THEN** the system uses that playbook for the briefing result

#### Scenario: Playbook is inferred from focus text
- **WHEN** a workflow market briefing request does not include a playbook identifier
- **AND** the request focus matches a playbook intent trigger
- **THEN** the system uses the matching playbook for the briefing result

#### Scenario: No playbook matches
- **WHEN** a workflow market briefing request does not include a playbook identifier
- **AND** no playbook intent trigger matches the request
- **THEN** the system uses a general market briefing playbook

### Requirement: Playbook results are source-grounded
The system SHALL represent selected playbook metadata, source grounding, and missing data gaps in workflow results.

#### Scenario: Playbook result includes metadata
- **WHEN** a workflow market briefing uses a financial analysis playbook
- **THEN** the workflow result includes the selected playbook identifier and display name
- **THEN** the workflow result includes required sources, optional sources, and output sections for that playbook

#### Scenario: Optional specialist data is unavailable
- **WHEN** a selected playbook references optional specialist data that is not available from current connectors
- **THEN** the workflow result includes explicit data gap entries for the unavailable data
- **THEN** the workflow does not invent values for the unavailable data

### Requirement: Playbooks remain research-only
The system SHALL frame playbook outputs as research and briefing support rather than live trading execution advice.

#### Scenario: FX carry playbook produces a result
- **WHEN** the FX carry playbook is used for a market briefing
- **THEN** the workflow result includes research-oriented language
- **THEN** the workflow result does not include live execution instructions or broker order directives
