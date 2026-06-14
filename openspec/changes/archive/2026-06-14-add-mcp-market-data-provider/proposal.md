## Why

AI Market Studio now has a workflow-first FX analysis path, but its deterministic mock market data still runs in-process through `MockConnector`. Introducing an MCP-backed mock market data provider lets the project validate MCP lifecycle, transport, failure handling, and provider isolation without changing the agent workflow surface or requiring a live data vendor.

## What Changes

- Add an internal MCP-backed market data provider option for FX spot rates, historical rates, and supported currency discovery.
- Add a local `ai-mcp-market-data` server that exposes deterministic mock market data through MCP tools.
- Add `MCPMarketDataConnector` as a `MarketDataConnector` implementation that hides MCP client logic from workflows.
- Add configuration to select market data provider implementation without changing `/api/chat` request shape.
- Keep model-facing chat tools unchanged: `collect_market_context`, `analyze_market_context`, and `generate_market_briefing`.
- Preserve existing `MockConnector` and `ExchangeRateHostConnector` behavior.
- Return connector errors or workflow data gaps cleanly when the MCP provider is unavailable; do not silently fall back in a way that hides provider failures.
- Do not add autonomy mode, direct model access to MCP tools, broker execution, or live vendor integrations in this change.

## Capabilities

### New Capabilities

- `mcp-market-data-provider`: MCP-backed market data provider support through an internal connector implementation and mock MCP server.

### Modified Capabilities

- `intent-level-agent-workflows`: Clarify that MCP-backed data remains an internal connector-backed implementation detail and is not exposed as a model-facing chat tool.

## Impact

- Backend connectors: new MCP client/connector implementation under `backend/connectors/`.
- MCP server: new local mock market data MCP server package or directory.
- Configuration: market data provider selection and MCP server command/timeout settings.
- Workflows: no model-facing tool changes; FX workflows may receive MCP-sourced rate/history data through the existing connector interface.
- Tests: unit tests for connector translation and MCP failures, MCP server tool tests, and chat/workflow integration tests proving the tool surface stays stable.
- Documentation: README architecture and MCP/FRED section updates to reflect MCP as a provider-layer integration rather than an agent-layer tool surface.
