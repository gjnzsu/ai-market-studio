## Context

AI Market Studio has a single workflow/playbook chat runtime. The model sees only intent-level workflow tools, while workflows obtain data through connector-backed implementation code. FX analysis now returns a structured `fx_analysis` payload, but local/test market data is still provided by the in-process `MockConnector`.

The MCP provider change should validate MCP integration without changing the agent design. The MCP server will initially act as an out-of-process mock market data provider, and the backend connector will hide MCP protocol details behind the existing `MarketDataConnector` interface.

## Goals / Non-Goals

**Goals:**

- Add an MCP-backed market data provider that can serve deterministic FX spot and historical rates.
- Keep workflow code dependent on `MarketDataConnector`, not on MCP protocol objects.
- Keep model-facing tools unchanged.
- Make MCP provider selection explicit through configuration.
- Preserve existing in-process mock and exchangerate.host providers.
- Surface MCP unavailability as explicit connector errors or workflow data gaps.
- Use the first version to validate MCP server lifecycle, request/response normalization, timeout behavior, and source labeling.

**Non-Goals:**

- Do not expose MCP tools directly to the chat model.
- Do not add autonomy mode or tool-discovery planning.
- Do not replace FRED direct API in this change.
- Do not integrate live vendor feeds such as Bloomberg or Refinitiv.
- Do not add broker execution, order routing, or trading advice.
- Do not make MCP a required dependency for default local development.

## Decisions

### MCP is a provider layer, not an agent layer

The model-facing tool set remains `collect_market_context`, `analyze_market_context`, and `generate_market_briefing`. MCP tools are only called by an internal connector implementation.

Alternatives considered:

- Expose MCP tools directly to the LLM. This would recreate the low-level tool-selection surface that the runtime consolidation deliberately removed.
- Make workflows call MCP directly. This would couple workflow logic to transport and lifecycle details that belong in provider adapters.

### Add `MCPMarketDataConnector`

The backend should add an implementation of `MarketDataConnector` that translates connector methods into MCP tool calls:

- `get_exchange_rate(base, target, date)` -> `get_fx_spot(pair, date?)`
- `get_exchange_rates(base, targets, date)` -> repeated or batched spot calls
- `get_historical_rates(base, targets, start_date, end_date)` -> `get_fx_history(pair, start_date, end_date)` per target
- `list_supported_currencies()` -> `list_supported_currencies()`

The connector should normalize MCP responses into the existing canonical dict shapes so workflow tests and UI contracts stay stable.

### Add a local mock MCP market data server

The first MCP server should be deterministic and mock-backed. It should expose MCP tools for:

- `get_fx_spot`
- `get_fx_history`
- `list_supported_currencies`

This intentionally mirrors current `MockConnector` behavior while exercising out-of-process protocol boundaries.

### Provider selection is explicit

Use a provider selection setting such as `MARKET_DATA_PROVIDER=mock|exchangerate_host|mcp`. MCP-specific settings should include the server command and timeout. Existing `USE_MOCK_CONNECTOR` can be supported during migration, but the new provider setting should become the clearer path.

### MCP failure must be visible

If MCP startup, timeout, or tool execution fails, the connector should raise a connector-layer error. Workflows that treat a source as optional may turn that into data gaps; required rate collection should not silently fall back to another provider unless a future spec explicitly adds fallback policy.

## Risks / Trade-offs

- [Risk] MCP adds process lifecycle and timeout complexity. -> Mitigation: start with a deterministic local mock server and explicit timeout tests.
- [Risk] Provider selection could become confusing with existing `USE_MOCK_CONNECTOR`. -> Mitigation: document precedence and migrate toward `MARKET_DATA_PROVIDER`.
- [Risk] Historical data shape may differ between existing connector and MCP tool response. -> Mitigation: normalize inside `MCPMarketDataConnector` and test against `MarketDataConnector` contract.
- [Risk] Treating MCP as a mock server could be mistaken for live data support. -> Mitigation: label source as `mcp-mock-market-data` and document that live vendor support is out of scope.
- [Risk] Silent fallback could hide MCP failures. -> Mitigation: fail visibly for required market data and represent optional gaps explicitly.

## Migration Plan

1. Add deterministic MCP server tools that match current mock market data semantics.
2. Add backend MCP client and `MCPMarketDataConnector`.
3. Add configuration for provider selection and MCP timeout/command.
4. Update app startup to instantiate the selected provider.
5. Add tests for server tools, connector normalization, provider selection, chat tool-surface stability, and failure handling.
6. Update README to describe MCP as a provider-layer integration.

## Open Questions

- Should the first MCP transport be stdio only, or should we also support HTTP/SSE for deployment parity?
- Should `get_fx_history` return one pair per call or support multiple targets in one MCP call?
- Should `USE_MOCK_CONNECTOR` remain indefinitely as an alias, or should it be marked deprecated after `MARKET_DATA_PROVIDER` lands?
