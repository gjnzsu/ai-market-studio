# mcp-market-data-provider Specification

## Purpose
TBD - created by archiving change add-mcp-market-data-provider. Update Purpose after archive.
## Requirements
### Requirement: MCP market data provider is available as an internal connector
The system SHALL support an MCP-backed market data provider through a `MarketDataConnector` implementation.

#### Scenario: MCP connector fetches spot FX data
- **WHEN** the selected market data provider is MCP and a workflow requests `EUR/USD` spot data
- **THEN** the backend calls the configured MCP market data server through the MCP connector
- **THEN** the workflow receives a canonical rate object containing `base`, `target`, `rate`, `date`, and `source`
- **THEN** the `source` identifies the MCP mock market data provider

#### Scenario: MCP connector fetches historical FX data
- **WHEN** the selected market data provider is MCP and a workflow requests historical rates for a supported pair and date range
- **THEN** the backend calls the configured MCP market data server through the MCP connector
- **THEN** the connector returns the existing historical rate shape keyed by date and target currency

#### Scenario: MCP connector lists supported currencies
- **WHEN** the selected market data provider is MCP and the backend lists supported currencies
- **THEN** the connector returns the supported ISO currency codes from the MCP server

### Requirement: MCP mock market data server exposes deterministic market data tools
The system SHALL provide a local MCP server that exposes deterministic mock market data for development and tests.

#### Scenario: MCP server exposes spot tool
- **WHEN** an MCP client calls `get_fx_spot` with a supported FX pair
- **THEN** the MCP server returns deterministic spot rate data for that pair
- **THEN** the response includes provider source metadata

#### Scenario: MCP server exposes history tool
- **WHEN** an MCP client calls `get_fx_history` with a supported FX pair and date range
- **THEN** the MCP server returns deterministic daily rates for that date range
- **THEN** repeated calls with the same inputs return the same values

#### Scenario: MCP server exposes currency discovery
- **WHEN** an MCP client calls `list_supported_currencies`
- **THEN** the MCP server returns the supported currency list

### Requirement: Market data provider selection is configurable
The system SHALL allow market data provider selection without changing chat request shape or workflow tool definitions.

#### Scenario: MCP provider is selected
- **WHEN** configuration selects the MCP market data provider
- **THEN** application startup creates an MCP-backed market data connector
- **THEN** `/api/chat` requests continue to use the existing workflow runtime

#### Scenario: Existing providers remain selectable
- **WHEN** configuration selects the in-process mock provider or exchangerate.host provider
- **THEN** application startup creates the corresponding existing connector
- **THEN** MCP is not required for those provider modes

### Requirement: MCP provider failures are visible
The system SHALL surface MCP startup, timeout, protocol, and tool execution failures through connector-layer errors or workflow data gaps.

#### Scenario: Required MCP rate request fails
- **WHEN** a workflow requires FX rate data from the MCP provider and the MCP request fails
- **THEN** the connector raises a connector-layer error
- **THEN** the system does not silently replace the MCP response with another provider's rate data

#### Scenario: Optional MCP-backed context is unavailable
- **WHEN** a workflow treats MCP-backed market context as optional and the MCP request fails
- **THEN** the workflow may return a data gap describing the unavailable MCP source
- **THEN** the analysis does not invent MCP-backed observations

### Requirement: MCP market data remains research-only
The system SHALL label first-version MCP market data as deterministic mock market data and not live trading data.

#### Scenario: MCP data appears in FX analysis
- **WHEN** FX analysis is grounded in MCP mock market data
- **THEN** source grounding identifies the data as MCP mock market data
- **THEN** the FX analysis remains `research_only`

