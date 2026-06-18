## ADDED Requirements

### Requirement: Gateway safety failures remain explicit in workflow chat
The system SHALL surface AI gateway safety failures during workflow chat execution as explicit gateway or safety errors without silently falling back to another orchestration path.

#### Scenario: Prompt is rejected by gateway safety policy
- **WHEN** a workflow chat request is rejected by the AI gateway input safety policy
- **THEN** AI Market Studio returns a clear chat API error identifying the AI gateway safety failure
- **THEN** AI Market Studio does not retry the request through legacy orchestration

#### Scenario: Model response is blocked by gateway safety policy
- **WHEN** the AI gateway blocks a model response due to output safety policy
- **THEN** AI Market Studio returns a clear chat API error identifying the AI gateway safety failure
- **THEN** AI Market Studio does not return unsafe model content to the frontend
