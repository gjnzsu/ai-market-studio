## ADDED Requirements

### Requirement: Legacy orchestration is the default
The system SHALL use the existing legacy chat orchestration path when a chat request does not explicitly request agent workflow mode.

#### Scenario: Chat request omits orchestration mode
- **WHEN** a client sends a valid `/api/chat` request with `message` and optional `history` only
- **THEN** the system uses legacy tool orchestration
- **THEN** the request does not expose intent-level agent workflow tools to the model

#### Scenario: Existing clients remain compatible
- **WHEN** an existing client sends a chat request using the current request shape
- **THEN** the system accepts the request without requiring any new field
- **THEN** the response remains compatible with the current `ChatResponse` shape

### Requirement: Agent workflow mode is explicit opt-in
The system SHALL run agent workflow orchestration only when the request explicitly selects agent workflow mode and agent workflow mode is enabled by configuration.

#### Scenario: Chat request selects workflow mode
- **WHEN** a client sends a valid `/api/chat` request that explicitly selects agent workflow mode
- **AND** agent workflow mode is enabled by configuration
- **THEN** the system uses agent workflow orchestration for that request
- **THEN** the system may expose intent-level agent workflow tools to the model

#### Scenario: Chat request selects legacy mode
- **WHEN** a client sends a valid `/api/chat` request that explicitly selects legacy mode
- **THEN** the system uses legacy tool orchestration
- **THEN** the request does not expose intent-level agent workflow tools to the model

### Requirement: Disabled workflow mode is predictable
The system SHALL handle requests for agent workflow mode predictably when agent workflow mode is disabled by configuration.

#### Scenario: Workflow mode requested while disabled
- **WHEN** a client sends a valid `/api/chat` request that explicitly selects agent workflow mode
- **AND** agent workflow mode is disabled by configuration
- **THEN** the system rejects the request with a clear client-facing error
- **THEN** the system does not silently run legacy orchestration for that request

### Requirement: Tool exposure is mode-specific
The system SHALL choose the model tool set according to the selected orchestration mode.

#### Scenario: Legacy mode tool set
- **WHEN** a chat request runs in legacy mode
- **THEN** the model receives only legacy-supported chat tools
- **THEN** low-level or intent-level agent workflow tools are not available to the model

#### Scenario: Agent workflow mode tool set
- **WHEN** a chat request runs in agent workflow mode
- **THEN** the model receives the approved intent-level agent workflow tools for that mode
- **THEN** overlapping low-level internal agent tools are not directly exposed unless explicitly approved by the workflow spec

### Requirement: Response contract remains backward compatible
The system SHALL preserve the existing chat response contract for both orchestration modes.

#### Scenario: Legacy mode response
- **WHEN** a chat request completes successfully in legacy mode
- **THEN** the response contains `reply`, `data`, and `tool_used` fields using the existing response shape

#### Scenario: Agent workflow mode response
- **WHEN** a chat request completes successfully in agent workflow mode
- **THEN** the response contains `reply`, `data`, and `tool_used` fields using the existing response shape
- **THEN** workflow-specific details are represented inside `data` or observability records without requiring a breaking response schema change
