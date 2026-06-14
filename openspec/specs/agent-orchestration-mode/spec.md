# agent-orchestration-mode Specification

## Purpose
TBD - created by archiving change agent-workflow-foundation. Update Purpose after archive.
## Requirements
### Requirement: Response contract remains backward compatible
The system SHALL preserve the existing chat response contract for the single workflow-based chat runtime.

#### Scenario: Chat runtime response
- **WHEN** a `/api/chat` request completes successfully
- **THEN** the response contains `reply`, `data`, and `tool_used` fields using the existing response shape
- **THEN** workflow-specific details are represented inside `data` or observability records without requiring a breaking response schema change

### Requirement: Chat uses a single workflow-based runtime
The system SHALL use the workflow-based chat agent runtime for every valid `/api/chat` request.

#### Scenario: Chat request omits orchestration mode
- **WHEN** a client sends a valid `/api/chat` request with `message` and optional `history`
- **THEN** the system uses the workflow-based chat runtime
- **THEN** the model receives the approved intent-level workflow tool set

#### Scenario: Chat request includes removed orchestration mode
- **WHEN** a client sends a `/api/chat` request containing `agent_mode`
- **THEN** the system rejects the request as invalid
- **THEN** the system does not run a legacy or workflow fallback based on that field

### Requirement: Workflow runtime is always enabled for chat
The system SHALL NOT require a workflow enablement flag before using the chat workflow runtime.

#### Scenario: Workflow enablement flag is absent
- **WHEN** the service starts without `ENABLE_AGENT_WORKFLOW_MODE`
- **THEN** valid `/api/chat` requests still use the workflow-based chat runtime
- **THEN** the request is not rejected because workflow mode is disabled

