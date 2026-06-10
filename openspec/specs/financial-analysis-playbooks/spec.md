# financial-analysis-playbooks Specification

## Purpose
Define runtime financial analysis playbooks that structure workflow-mode market briefings with source requirements, output sections, data-gap discipline, and research-only boundaries.

## Requirements
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
The system SHALL represent selected playbook metadata, source grounding, synthetic specialist data usage, and missing data gaps in workflow results.

#### Scenario: Playbook result includes metadata
- **WHEN** a workflow market briefing uses a financial analysis playbook
- **THEN** the workflow result includes the selected playbook identifier and display name
- **THEN** the workflow result includes required sources, optional sources, and output sections for that playbook

#### Scenario: Optional specialist data is unavailable
- **WHEN** a selected playbook references optional specialist data that is not available from current connectors or synthetic specialist data
- **THEN** the workflow result includes explicit data gap entries for the unavailable data
- **THEN** the workflow does not invent values for the unavailable data

#### Scenario: Synthetic specialist data is available
- **WHEN** the FX carry playbook uses synthetic forward curve and implied volatility data
- **THEN** the workflow result identifies those inputs as synthetic specialist data
- **THEN** source grounding reports those inputs separately from connector-backed available sources
- **THEN** the workflow result does not report those synthetic inputs as unavailable data gaps

### Requirement: Playbooks remain research-only
The system SHALL frame playbook outputs as research and briefing support rather than live trading execution advice.

#### Scenario: FX carry playbook produces a result
- **WHEN** the FX carry playbook is used for a market briefing
- **THEN** the workflow result includes research-oriented language
- **THEN** the workflow result does not include live execution instructions or broker order directives

#### Scenario: FX carry playbook uses synthetic demo metrics
- **WHEN** the FX carry playbook includes synthetic specialist data and carry metrics
- **THEN** the workflow result identifies the metrics as research-only demo support
- **THEN** the workflow result does not imply that synthetic metrics are live trading signals

### Requirement: FX carry playbook produces deterministic demo metrics
The system SHALL enrich FX carry playbook results with deterministic demo metrics when synthetic specialist data is available.

#### Scenario: Synthetic FX carry metrics are included
- **WHEN** a workflow market briefing uses the FX carry playbook
- **AND** synthetic specialist data is available
- **THEN** the workflow result includes a synthetic forward curve
- **THEN** the workflow result includes synthetic implied volatility
- **THEN** the workflow result includes lightweight carry metrics derived from the available context and synthetic specialist data

#### Scenario: Synthetic FX carry metrics are stable
- **WHEN** the FX carry playbook is run repeatedly with the same pair and input context
- **THEN** the synthetic specialist data and carry metrics are deterministic enough for unit tests to assert exact or bounded values

### Requirement: Financial analysis playbooks use runtime primitive definitions
The system SHALL represent financial analysis playbooks through the playbook runtime primitive layer while preserving their existing identifiers, source requirements, output sections, research-only framing, and workflow response shape.

#### Scenario: Existing playbook metadata is preserved
- **WHEN** the system exposes financial analysis playbook metadata in a workflow market briefing result
- **THEN** the result includes the same playbook identifier, display name, required sources, optional sources, output sections, and research-only flag expected for that playbook

#### Scenario: Existing FX carry demo behavior is preserved
- **WHEN** a workflow market briefing uses the FX carry playbook
- **AND** deterministic synthetic specialist data is available
- **THEN** the workflow result includes synthetic forward curve data
- **THEN** the workflow result includes synthetic implied volatility data
- **THEN** the workflow result includes carry metrics derived from the available context and synthetic specialist data

#### Scenario: Existing data-gap behavior is preserved
- **WHEN** a workflow market briefing uses a financial analysis playbook
- **THEN** unavailable specialist sources are represented as data gaps unless the selected runtime profile provides synthetic specialist data for those sources
