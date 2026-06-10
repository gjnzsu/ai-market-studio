# playbook-runtime-primitives Specification

## Purpose
Define the backend runtime primitive layer used to compose, select, and explain financial analysis playbooks while preserving deterministic demo behavior and research-only boundaries.

## Requirements
### Requirement: Runtime playbooks are composed from primitives
The system SHALL represent backend financial analysis playbooks as runtime definitions composed from identity, source contract, output contract, runtime profile, and rule primitives.

#### Scenario: Playbook definition exposes primitive contracts
- **WHEN** the system initializes the playbook runtime registry
- **THEN** each playbook definition includes identity metadata
- **THEN** each playbook definition includes a source contract
- **THEN** each playbook definition includes an output contract
- **THEN** each playbook definition includes runtime profile and rule metadata

### Requirement: Runtime primitive registry preserves existing playbook selection
The system SHALL select playbooks from the runtime primitive registry using explicit playbook identifiers or inferred intent triggers.

#### Scenario: Explicit runtime playbook selection
- **WHEN** a workflow market briefing request includes a supported playbook identifier
- **THEN** the runtime primitive registry returns the matching playbook definition

#### Scenario: Inferred runtime playbook selection
- **WHEN** a workflow market briefing request omits a playbook identifier
- **AND** the request focus matches a runtime playbook intent trigger
- **THEN** the runtime primitive registry returns the matching playbook definition

#### Scenario: Runtime playbook fallback
- **WHEN** a workflow market briefing request does not match any specialized runtime playbook
- **THEN** the runtime primitive registry returns the general market briefing playbook definition

### Requirement: Runtime profiles control demo specialist data behavior
The system SHALL use runtime profile metadata to determine whether a playbook can include deterministic synthetic specialist data for demo and test support.

#### Scenario: FX carry synthetic profile applies
- **WHEN** a workflow market briefing uses the FX carry runtime playbook
- **AND** the FX carry runtime definition includes a synthetic specialist data profile
- **THEN** the workflow may include deterministic synthetic forward curve and implied volatility inputs
- **THEN** the workflow identifies those inputs as synthetic rather than connector-backed market data

#### Scenario: Synthetic profile is absent
- **WHEN** a workflow market briefing uses a runtime playbook without a synthetic specialist data profile
- **THEN** the workflow does not create synthetic specialist data for that playbook

### Requirement: Runtime rules preserve research-only and source-grounding boundaries
The system SHALL apply runtime rule metadata so playbook outputs remain source-grounded and research-only.

#### Scenario: Source grounding rule is applied
- **WHEN** a workflow market briefing uses a runtime playbook definition
- **THEN** the workflow result reports requested sources, available connector-backed sources, synthetic sources, missing required sources, and missing optional sources

#### Scenario: Research-only rule is applied
- **WHEN** a workflow market briefing uses a runtime playbook definition
- **THEN** the workflow result frames the output as research and briefing support
- **THEN** the workflow result does not include live execution instructions or broker order directives
