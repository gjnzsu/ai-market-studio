# synthetic-specialist-data Specification

## Purpose
Provide deterministic, clearly labeled synthetic specialist data for demo and test workflows without representing the values as live market quotes.

## Requirements
### Requirement: Synthetic specialist data is deterministic
The system SHALL provide deterministic synthetic specialist data for supported demo workflows.

#### Scenario: Synthetic forward curve is generated for an FX pair
- **WHEN** the system requests synthetic forward curve data for a supported FX pair
- **THEN** the result includes the FX pair, tenor-level forward rates, tenor-level forward points, an as-of date, and `source` set to `synthetic`
- **THEN** repeated requests with the same input produce the same tenor values

#### Scenario: Synthetic implied volatility is generated for an FX pair
- **WHEN** the system requests synthetic implied volatility data for a supported FX pair
- **THEN** the result includes the FX pair, tenor-level ATM volatility values, an as-of date, and `source` set to `synthetic`
- **THEN** repeated requests with the same input produce the same tenor values

### Requirement: Synthetic specialist data has explicit provenance
The system SHALL label synthetic specialist data separately from connector-backed market data.

#### Scenario: Synthetic data appears in workflow output
- **WHEN** a workflow result includes synthetic specialist data
- **THEN** the result identifies the data as synthetic
- **THEN** the result does not describe the synthetic values as live market quotes

#### Scenario: Synthetic source grounding is reported separately
- **WHEN** a workflow uses synthetic specialist data alongside connector-backed data
- **THEN** source grounding identifies synthetic sources separately from connector-backed available sources

### Requirement: Synthetic carry metrics are lightweight and research-only
The system SHALL calculate deterministic demo metrics from synthetic specialist data without producing trading execution instructions.

#### Scenario: Carry metrics are calculated
- **WHEN** an FX carry workflow has spot context and synthetic specialist data
- **THEN** the result includes deterministic carry metrics such as a rate differential proxy, forward premium or discount, and carry-to-vol indicator
- **THEN** the metric names and interpretation make clear that they are research and demo support metrics

#### Scenario: Trading execution instructions are not produced
- **WHEN** synthetic carry metrics are included in a workflow result
- **THEN** the result does not include broker order directives, position sizing, stop-loss levels, take-profit levels, or live execution instructions
