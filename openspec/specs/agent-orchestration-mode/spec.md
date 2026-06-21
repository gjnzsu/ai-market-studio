# agent-orchestration-mode Specification

## Purpose
Define the supported chat orchestration mode and response contract for AI Market Studio.

## Requirements
### Requirement: Workflow orchestration is the default
The system SHALL use workflow chat orchestration when a chat request does not specify an agent orchestration mode.

#### Scenario: Chat request omits agent mode
- **WHEN** a client sends a valid `/api/chat` request without `agent_mode`
- **THEN** the system uses workflow orchestration
- **THEN** the request may expose approved intent-level agent workflow tools to the model

### Requirement: Agent workflow mode is the supported chat orchestration mode
The system SHALL run agent workflow orchestration for supported chat requests and SHALL NOT support legacy orchestration as a product mode.

#### Scenario: Chat request selects workflow mode
- **WHEN** a client sends a valid `/api/chat` request that explicitly selects agent workflow mode
- **AND** agent workflow mode is enabled by configuration
- **THEN** the system uses agent workflow orchestration for that request
- **THEN** the system may expose intent-level agent workflow tools to the model

#### Scenario: Chat request selects legacy mode
- **WHEN** a client sends a `/api/chat` request that explicitly selects legacy mode
- **THEN** the system rejects the request as unsupported
- **THEN** the system does not run legacy tool orchestration

### Requirement: Disabled workflow mode is predictable
The system SHALL handle workflow availability predictably when workflow mode is disabled by configuration.

#### Scenario: Workflow mode disabled
- **WHEN** a client sends a valid `/api/chat` request
- **AND** workflow mode is disabled by configuration
- **THEN** the system returns a clear workflow-disabled response
- **THEN** the system does not silently run legacy orchestration

### Requirement: Tool exposure is mode-safe
The system SHALL expose only approved workflow tools to the model for chat orchestration.

#### Scenario: Workflow tool set
- **WHEN** a chat request runs through the supported workflow orchestration path
- **THEN** the model receives the approved intent-level agent workflow tools
- **THEN** overlapping low-level internal agent tools are not directly exposed unless explicitly approved by the workflow specification

### Requirement: Response shape remains stable across orchestration cleanup
The system SHALL preserve the `/api/chat` response shape while removing legacy orchestration.

#### Scenario: Workflow response
- **WHEN** a chat request completes successfully
- **THEN** the response includes `reply`, `data`, and `tool_used`
- **THEN** workflow-specific details are represented inside `data` or observability records without requiring a breaking response schema change
