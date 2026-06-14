## 1. MCP Server Contract

- [x] 1.1 Add tests for MCP mock market data spot-rate tool behavior.
- [x] 1.2 Add tests for MCP mock market data historical-rate tool behavior.
- [x] 1.3 Add tests for MCP supported-currency discovery behavior.
- [x] 1.4 Implement the local mock market data MCP server tools.

## 2. Backend MCP Connector

- [x] 2.1 Add tests for `MCPMarketDataConnector.get_exchange_rate` response normalization.
- [x] 2.2 Add tests for `MCPMarketDataConnector.get_historical_rates` response normalization.
- [x] 2.3 Add tests for `MCPMarketDataConnector.list_supported_currencies`.
- [x] 2.4 Add tests proving MCP failures raise connector-layer errors.
- [x] 2.5 Implement backend MCP client and `MCPMarketDataConnector`.

## 3. Provider Configuration

- [x] 3.1 Add settings tests for market data provider selection and MCP-specific settings.
- [x] 3.2 Add startup tests proving `MARKET_DATA_PROVIDER=mcp` creates the MCP connector.
- [x] 3.3 Preserve existing mock and exchangerate.host provider startup behavior.
- [x] 3.4 Implement provider selection configuration and startup wiring.

## 4. Workflow and Agent Integration

- [x] 4.1 Add workflow tests proving MCP-sourced spot data can ground `fx_analysis`.
- [x] 4.2 Add workflow tests proving MCP-sourced history improves FX trend/volatility sections.
- [x] 4.3 Add agent/tool-surface tests proving MCP tools are not model-facing.
- [x] 4.4 Add chat API/e2e test for MCP provider returning `fx_analysis` data.
- [x] 4.5 Add failure-path test for MCP provider unavailability.

## 5. Documentation

- [x] 5.1 Update README architecture to describe MCP as a provider-layer integration.
- [x] 5.2 Update MCP/FRED documentation to remove stale model-facing low-level tool references.
- [x] 5.3 Document local MCP mock market data server usage and configuration.

## 6. Verification

- [x] 6.1 Run targeted MCP server and connector tests.
- [x] 6.2 Run targeted workflow, agent, and chat API tests.
- [x] 6.3 Run OpenSpec validation for `add-mcp-market-data-provider`.
