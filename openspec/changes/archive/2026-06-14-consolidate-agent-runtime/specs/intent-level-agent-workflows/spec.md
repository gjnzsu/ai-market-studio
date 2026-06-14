## MODIFIED Requirements

### Requirement: Workflows represent customer intents
The system SHALL expose chat agent tools around customer intents rather than exposing low-level internal agent steps directly.

#### Scenario: Model receives intent-level workflow tools
- **WHEN** a chat request runs through the single chat agent runtime
- **THEN** the model receives tools for customer intents such as collecting market context, analyzing market context, and generating a market briefing
- **THEN** the model does not need to manually chain low-level data collection, analysis, synthesis, and report-generation tools to satisfy the intent

### Requirement: Market briefing replaces legacy market insight
The system SHALL replace the existing legacy market insight tool with the market briefing workflow for market insight, overview, briefing, and multi-source synthesis intents.

#### Scenario: Market insight request
- **WHEN** a customer asks for a market insight, briefing, overview, or multi-source synthesis
- **THEN** the system uses the market briefing workflow
- **THEN** the system does not expose or call the legacy market insight tool for that intent

#### Scenario: Legacy market insight tool is removed from approved tool sets
- **WHEN** the system builds the model-facing chat tool set
- **THEN** the legacy market insight tool is not included in the approved tool set
- **THEN** market insight behavior is provided by the market briefing workflow

#### Scenario: Existing chat clients ask for market insight
- **WHEN** an existing client sends a chat request asking for a market insight without depending on a specific tool name
- **THEN** the system continues to return a compatible chat response
- **THEN** the response may report the market briefing workflow as the tool used

### Requirement: Internal agents remain internal implementation units
The system SHALL treat data collection, market analysis, research synthesis, and output assembly units as internal workflow implementation details unless a workflow spec explicitly exposes them.

#### Scenario: Low-level internal agent functions exist in the codebase
- **WHEN** low-level internal agent functions exist for data collection, market analysis, research synthesis, or output assembly
- **THEN** those functions may be reused by intent-level workflows
- **THEN** those functions are not directly exposed to the model-facing chat tool set unless explicitly approved by the workflow specification

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

## ADDED Requirements

### Requirement: Chat exposes only approved intent-level workflow tools
The system SHALL expose only approved intent-level workflow tools to the chat model.

#### Scenario: Chat model tool set is built
- **WHEN** the system builds the model-facing chat tool set
- **THEN** the tool set contains `collect_market_context`, `analyze_market_context`, and `generate_market_briefing`
- **THEN** the tool set does not contain low-level connector tools or legacy sub-agent tools

#### Scenario: Low-level FX data is needed
- **WHEN** a chat workflow needs spot rates, historical rates, news, economic indicators, or research context
- **THEN** the workflow obtains that data through internal connector-backed implementation code
- **THEN** the model is not required to call low-level connector tools directly
