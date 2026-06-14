## MODIFIED Requirements

### Requirement: Market analysis is separate from full briefing generation
The system SHALL provide a market analysis workflow that analyzes market context without requiring full briefing generation.

#### Scenario: Customer asks for trend or economic analysis
- **WHEN** a customer asks to analyze a currency pair, market trend, volatility, signal, or economic relationship
- **THEN** the model may call the market analysis workflow
- **THEN** the workflow returns analysis results grounded in collected or supplied context
- **THEN** the workflow does not generate a full market briefing unless the customer asks for one

#### Scenario: Customer asks for FX pair analysis
- **WHEN** a customer asks to analyze one or more FX pairs
- **THEN** the market analysis workflow may return an FX-specific `fx_analysis` payload
- **THEN** the result remains compatible with the chat response `data` field
- **THEN** the workflow does not require the model to manually chain low-level data collection, analysis, synthesis, and report-generation tools

## ADDED Requirements

### Requirement: Market analysis accepts FX analysis parameters
The system SHALL allow the market analysis workflow to receive optional FX analysis parameters without adding a new model-facing tool.

#### Scenario: Analysis horizon is supplied
- **WHEN** the model calls `analyze_market_context` with an analysis horizon
- **THEN** the workflow includes that horizon in the FX analysis result
- **THEN** the workflow uses the horizon to label or scope first-version analysis sections

#### Scenario: Analysis focus is supplied
- **WHEN** the model calls `analyze_market_context` with a focus value
- **THEN** the workflow includes the focus in the FX analysis result
- **THEN** the workflow does not treat the focus as permission to invent missing source data
