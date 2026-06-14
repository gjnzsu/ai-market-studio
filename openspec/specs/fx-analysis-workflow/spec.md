# fx-analysis-workflow Specification

## Purpose
TBD - created by archiving change add-fx-analysis-workflow. Update Purpose after archive.
## Requirements
### Requirement: FX analysis returns a stable structured payload
The system SHALL provide a workflow-generated FX analysis payload for FX pair analysis requests.

#### Scenario: Single pair FX analysis
- **WHEN** a customer asks to analyze one FX pair
- **THEN** the workflow result includes `type` set to `fx_analysis`
- **THEN** the result includes the analyzed pair, analysis horizon, market context summary, analysis sections, scenarios, data gaps, confidence, and research-only framing

#### Scenario: Multi-pair FX analysis
- **WHEN** a customer asks to analyze multiple FX pairs
- **THEN** the workflow result includes the requested pairs
- **THEN** the result identifies a primary pair or represents per-pair summaries
- **THEN** the result does not merge unrelated pair context without labeling which pair each observation belongs to

### Requirement: FX analysis is source-grounded
The system SHALL ground FX analysis in supplied or collected market context and represent missing sources explicitly.

#### Scenario: Required rate context is available
- **WHEN** the workflow has rate context for the requested pair
- **THEN** the analysis includes the available rate context in its market context summary
- **THEN** the analysis derives trend, momentum, and volatility only from available rate observations

#### Scenario: Optional sources are unavailable
- **WHEN** news, FRED indicators, or research context is unavailable
- **THEN** the analysis includes data gap entries for unavailable optional sources that are relevant to the requested analysis
- **THEN** the analysis does not invent source-backed drivers for unavailable sources

#### Scenario: Research context includes sources
- **WHEN** research context includes document sources
- **THEN** the analysis includes source names or identifiers in source grounding
- **THEN** the final response can cite those research sources by name

### Requirement: FX analysis includes first-version analyst sections
The system SHALL organize first-version FX analysis into predictable sections.

#### Scenario: Analysis sections are generated
- **WHEN** FX analysis completes
- **THEN** the result includes sections for trend, volatility, drivers, scenarios, watch items, and limitations
- **THEN** each section can be empty or marked insufficient when supporting data is unavailable

#### Scenario: Scenario view is generated
- **WHEN** FX analysis completes
- **THEN** the result includes bull, base, and bear scenario descriptions
- **THEN** those scenarios are framed as research scenarios rather than trade instructions

### Requirement: FX analysis remains research-only
The system SHALL frame FX analysis as research support rather than live trading execution advice.

#### Scenario: FX analysis produces a view
- **WHEN** the workflow returns an FX analysis result
- **THEN** the result includes `research_only` set to true
- **THEN** the result avoids broker order directives, live execution instructions, and imperative trade commands

### Requirement: FX analysis handles compact pair notation
The system SHALL accept common compact six-letter FX pair notation when collecting or analyzing market context.

#### Scenario: Compact pair is supplied
- **WHEN** the workflow receives `EURUSD` as a requested pair
- **THEN** the workflow normalizes the pair to `EUR/USD`
- **THEN** the analysis proceeds against base `EUR` and target `USD`

