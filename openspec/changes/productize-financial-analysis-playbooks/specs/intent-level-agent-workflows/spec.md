## MODIFIED Requirements

### Requirement: Market briefing coordinates internal workflow steps
The system SHALL provide a market briefing workflow that coordinates the required internal steps for a multi-source market explanation and may apply a financial analysis playbook when the user asks for a specialized briefing format.

#### Scenario: Customer asks for a market briefing
- **WHEN** a customer asks for a briefing, overview, explanation, or synthesis of what is happening with one or more currency pairs
- **THEN** the model may call the market briefing workflow
- **THEN** the workflow coordinates collection, analysis, and synthesis internally as needed
- **THEN** the model receives one structured workflow result instead of orchestrating each internal step directly

#### Scenario: Customer asks for a specialized financial briefing
- **WHEN** a customer asks for a carry, macro-rates, morning note, or catalyst-calendar style market briefing
- **THEN** the market briefing workflow may apply the matching financial analysis playbook
- **THEN** the workflow result includes the selected playbook and data gaps inside the structured data payload

### Requirement: Workflow results are structured for chat rendering
The system SHALL return structured workflow results that can be carried through the existing chat response contract, including financial analysis playbook details when a playbook is used.

#### Scenario: Workflow returns data to chat response
- **WHEN** an intent-level workflow completes successfully
- **THEN** the workflow result includes a stable `type` identifier and structured data for the completed intent
- **THEN** the chat response can include the workflow result in `data` without requiring a breaking response schema change

#### Scenario: Playbook result returns through chat response
- **WHEN** a workflow market briefing uses a financial analysis playbook
- **THEN** the chat response still contains `reply`, `data`, and `tool_used`
- **THEN** the selected playbook, source grounding, and data gaps are represented inside `data`
