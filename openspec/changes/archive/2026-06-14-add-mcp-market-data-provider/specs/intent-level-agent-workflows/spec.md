## ADDED Requirements

### Requirement: MCP-backed data remains internal to workflows
The system SHALL treat MCP-backed market data as an internal connector-backed implementation detail rather than a model-facing chat tool surface.

#### Scenario: Chat model tool set with MCP provider configured
- **WHEN** the system builds the model-facing chat tool set while the MCP market data provider is configured
- **THEN** the tool set still contains only `collect_market_context`, `analyze_market_context`, and `generate_market_briefing`
- **THEN** MCP server tools such as `get_fx_spot`, `get_fx_history`, and `list_supported_currencies` are not exposed to the chat model

#### Scenario: Workflow uses MCP-backed market data
- **WHEN** a chat workflow needs FX spot or historical rates and the MCP market data provider is configured
- **THEN** the workflow obtains that data through the internal MCP-backed market data connector
- **THEN** the workflow result remains compatible with the existing chat response `data` field
