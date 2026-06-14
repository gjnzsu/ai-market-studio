## Why

AI Market Studio currently carries two chat-agent runtimes: the default legacy tool path and the opt-in workflow path. This makes the codebase harder to reason about and creates ambiguity for future FX analysis work, because new capabilities must decide whether to support legacy tools, workflow tools, or both.

The workflow/playbook path is the clearer product direction. Consolidating chat onto that runtime removes obsolete compatibility concerns and gives FX analysis a single architecture to extend.

## What Changes

- **BREAKING**: Remove `agent_mode` as a client-selectable chat request field.
- **BREAKING**: Remove the legacy chat tool runtime as a supported `/api/chat` behavior.
- Make the intent-level workflow runtime the only model-facing chat runtime.
- Remove `ENABLE_AGENT_WORKFLOW_MODE` as a feature gate; workflow behavior is always enabled for chat.
- Keep useful runtime settings, such as timeout and max rounds, under neutral agent-runtime names if they are still needed.
- Reduce model-facing tools to intent-level workflow tools:
  - `collect_market_context`
  - `analyze_market_context`
  - `generate_market_briefing`
- Keep connector-backed low-level capabilities as internal implementation details rather than model-facing tools.
- Reposition or remove legacy sub-agent modules and dispatch branches that are no longer reachable through the single runtime.
- Update tests and documentation so they describe one chat runtime, not legacy/workflow mode selection.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `agent-orchestration-mode`: Replace dual legacy/workflow orchestration with a single workflow-based chat runtime.
- `intent-level-agent-workflows`: Make intent-level workflow tools the only model-facing chat tool set and clarify that low-level agents remain internal implementation units.
- `agent-workflow-guardrails`: Remove legacy-mode isolation guardrails and update workflow guardrails for the single chat runtime.

## Impact

- API: `/api/chat` no longer accepts or honors `agent_mode`.
- Backend models: `ChatRequest` no longer includes `agent_mode`.
- Backend runtime: `backend/agent/agent.py` no longer branches by orchestration mode.
- Tool registry: `backend/agent/tools.py` exposes only workflow tools to the model-facing agent.
- Internal implementation: low-level connector calls and specialist analysis remain available through workflow implementation code.
- Configuration: workflow enablement flag is removed; timeout/max-round settings may be renamed.
- Tests: legacy-mode tests are removed or rewritten to assert the single workflow runtime.
- Documentation: README and architecture docs are updated to remove legacy compatibility language.
