## ADDED Requirements

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
