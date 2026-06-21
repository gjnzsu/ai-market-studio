# intent-level-agent-workflows Specification

## Purpose
TBD - created by archiving change agent-workflow-foundation. Update Purpose after archive.
## Requirements
### Requirement: Workflows represent customer intents
The system SHALL expose agent workflow tools around customer intents rather than exposing low-level internal agent steps directly.

#### Scenario: Model receives intent-level workflow tools
- **WHEN** a chat request runs in agent workflow mode
- **THEN** the model may receive tools for customer intents such as collecting market context, analyzing market context, and generating a market briefing
- **THEN** the model does not need to manually chain low-level data collection, analysis, synthesis, and report-generation tools to satisfy the intent

### Requirement: Market context collection is data-only
The system SHALL provide a market context collection workflow that retrieves requested market context without performing analysis or generating a briefing.

#### Scenario: Customer asks only to collect market context
- **WHEN** a customer asks for market data, news, economic indicators, or research sources without asking for analysis or a briefing
- **THEN** the model may call the market context collection workflow
- **THEN** the workflow returns collected context only
- **THEN** the workflow does not run market analysis or research synthesis steps

### Requirement: Market analysis is separate from full briefing generation
The system SHALL provide a market analysis workflow that analyzes market context without requiring full briefing generation.

#### Scenario: Customer asks for trend or economic analysis
- **WHEN** a customer asks to analyze a currency pair, market trend, volatility, signal, or economic relationship
- **THEN** the model may call the market analysis workflow
- **THEN** the workflow returns analysis results grounded in collected or supplied context
- **THEN** the workflow does not generate a full market briefing unless the customer asks for one

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

### Requirement: Market briefing replaces legacy market insight
The system SHALL replace the existing legacy market insight tool with the market briefing workflow for market insight, overview, briefing, and multi-source synthesis intents.

#### Scenario: Workflow mode market insight request
- **WHEN** a chat request runs in agent workflow mode
- **AND** the customer asks for a market insight, briefing, overview, or multi-source synthesis
- **THEN** the system uses the market briefing workflow
- **THEN** the system does not expose or call the legacy market insight tool for that intent

#### Scenario: Legacy market insight tool is removed from approved tool sets
- **WHEN** the system builds the model tool set for either orchestration mode
- **THEN** the legacy market insight tool is not included in the approved tool set
- **THEN** market insight behavior is provided by the market briefing workflow or by lower-level legacy tools that remain explicitly approved for legacy mode

#### Scenario: Existing chat clients ask for market insight
- **WHEN** an existing client sends a chat request asking for a market insight without depending on a specific tool name
- **THEN** the system continues to return a compatible chat response
- **THEN** the response may report the new market briefing workflow as the tool used

### Requirement: Internal agents remain internal implementation units
The system SHALL treat data collection, market analysis, research synthesis, and output assembly units as internal workflow implementation details unless a workflow spec explicitly exposes them.

#### Scenario: Low-level internal agent tools exist in the codebase
- **WHEN** low-level internal agent functions exist for data collection, market analysis, research synthesis, or output assembly
- **THEN** those functions may be reused by intent-level workflows
- **THEN** those functions are not directly exposed to the model as workflow-mode tools unless explicitly approved by the workflow specification

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

### Requirement: ### Requirement: Workflow behavior is compatible with gateway-routed AI traffic
The system SHALL preserve intent-level workflow behavior when AI chat completions are routed through Kong Gateway.

#### Scenario: Model receives workflow tools through gateway-routed completion
- **WHEN** a chat request runs through workflow orchestration
- **AND** AI chat completion traffic is routed through Kong Gateway
- **THEN** the model receives approved intent-level workflow tools
- **THEN** the workflow result can be returned through the existing chat response contract

#### Scenario: Market briefing through gateway-routed completion
- **WHEN** a customer asks for a market briefing
- **AND** AI chat completion traffic is routed through Kong Gateway
- **THEN** the system uses the market briefing workflow
- **THEN** the model receives one structured workflow result instead of orchestrating internal steps directly

### Requirement: Workflow mode does not depend on legacy fallback
The system SHALL complete or fail workflow requests without falling back to legacy orchestration.

#### Scenario: Workflow tool fails under gateway routing
- **WHEN** a workflow tool fails while AI traffic is gateway-routed
- **THEN** the system returns a workflow failure or partial workflow result according to workflow guardrails
- **THEN** the system does not re-run the request with legacy tools
