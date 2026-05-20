## Why

AI Market Studio already has a multi-agent/sub-agent architecture in the codebase, but the current agent boundaries are unclear and overlapping, and direct multi-agent orchestration makes the model responsible for too much routing logic. We need to redesign the architecture around stable customer-intent workflows before enabling broader multi-agent behavior, while protecting the currently stable legacy chat path.

## What Changes

- Review and redesign the existing sub-agent model instead of re-enabling the previous four-agent choreography as-is.
- Add explicit opt-in access for the redesigned agent workflow mode, while keeping legacy tool orchestration as the default.
- Replace direct exposure of overlapping low-level sub-agent tools with stable intent-level workflow tools where appropriate.
- Replace the existing legacy `generate_market_insight` tool with the new market briefing workflow instead of keeping both long-term paths.
- Keep internal agent units focused and reusable, such as data collection, market analysis, research synthesis, and output assembly, without requiring the LLM to manually chain every step.
- Support simple customer intents, such as data collection, without forcing them through a full briefing or report workflow.
- Add acceptance requirements for bounded execution, timeout behavior, observability, and mode-specific tool exposure.
- Keep separated multi-agent runtime behavior out of scope for this change; this proposal creates the foundation for that future work.
- No breaking request/response schema changes: existing chat requests continue to work without specifying an agent mode, though market insight handling may move to the new workflow implementation.

## Capabilities

### New Capabilities

- `agent-orchestration-mode`: Defines how chat requests select between legacy tool orchestration and opt-in agent workflow orchestration.
- `intent-level-agent-workflows`: Defines customer-intent tools that may use internal agents without exposing fragile multi-step choreography to the LLM.
- `agent-workflow-guardrails`: Defines runtime limits, observability, timeout, and safe fallback requirements for running redesigned agent workflows.

### Modified Capabilities

- None. There are no existing OpenSpec capabilities in `openspec/specs/` yet.

## Impact

- Affected backend API: `/api/chat` request handling and `ChatRequest` schema.
- Affected agent runtime: `backend/agent/agent.py` prompt selection, tool definition selection, and tool-call execution behavior.
- Affected tool layer: `backend/agent/tools.py` may need mode-aware tool grouping and new intent-level workflow tools.
- Affected internal agents: `backend/agents/*` may be consolidated, renamed, or narrowed to remove boundary overlap.
- Affected configuration: add a disabled-by-default setting for agent workflow availability.
- Affected tests: add coverage for default legacy behavior, opt-in workflow behavior, market insight replacement behavior, data-only workflows, disabled-mode handling, timeout boundaries, and internal agent regressions.
