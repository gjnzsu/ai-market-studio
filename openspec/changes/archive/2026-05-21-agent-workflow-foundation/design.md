## Context

AI Market Studio currently exposes legacy chat tools and four sub-agent-style tools from the same global tool list. The sub-agent functions live in `backend/agents/`, but they are Python workflow helpers rather than separated agent runtimes. The previous direct multi-agent orchestration made the model decide too much choreography, which increased complexity and latency.

This change creates a safer foundation: `/api/chat` keeps legacy behavior by default, agent workflow mode is explicit and disabled-by-default, and model-facing workflow tools are shaped around customer intents instead of low-level internal agent steps.

## Goals / Non-Goals

**Goals:**

- Keep existing chat request/response compatibility.
- Add explicit orchestration mode selection with legacy as the default.
- Replace `generate_market_insight` with a market briefing workflow instead of keeping two long-term insight paths.
- Expose intent-level workflow tools in workflow mode: market context collection, market context analysis, and market briefing.
- Reuse or reshape existing internal agent functions behind the workflow layer.
- Add runtime, step, failure, and observability guardrails for workflow mode.

**Non-Goals:**

- No separated multi-agent runtime, agent memory, async job lifecycle, or user-created agents.
- No frontend UI changes are required for the first implementation.
- No breaking change to the `/api/chat` response schema.
- No silent fallback from workflow mode to legacy mode after workflow selection.

## Decisions

### 1. Use mode-specific tool sets

Create separate model-facing tool sets instead of sending the current global `TOOL_DEFINITIONS` to every chat request.

- `legacy` mode exposes approved direct tools only.
- `workflow` mode exposes approved intent-level workflow tools.
- Low-level internal agent tools such as `collect_market_data`, `analyze_market_trends`, `synthesize_research`, and `generate_report` are not model-facing workflow tools.
- `generate_market_insight` is removed from approved model-facing tool sets and replaced by the market briefing workflow.

Alternative considered: keep all tools exposed and rely on prompt instructions. This preserves too much ambiguity and repeats the original failure mode.

### 2. Add explicit orchestration mode selection

Extend chat handling with an optional mode selector, using legacy mode when omitted. Workflow mode requires both request selection and enabled configuration.

- Default request path remains legacy.
- If workflow mode is requested while disabled, return a clear client-facing error.
- The legacy path remains isolated from workflow failures.

Alternative considered: infer workflow mode automatically from the prompt. This would hide routing decisions and make debugging harder during stabilization.

### 3. Introduce an intent-level workflow layer

Add workflow functions that represent customer intents:

- `collect_market_context`: collects requested rates, news, FRED, and research context without analysis.
- `analyze_market_context`: analyzes collected or supplied market context without generating a full briefing.
- `generate_market_briefing`: coordinates collection, analysis, and synthesis for market insight, overview, briefing, and multi-source synthesis intents.

These workflows may reuse existing internal units, but the implementation can narrow, rename, or consolidate current `backend/agents/*` boundaries where they overlap.

Alternative considered: expose the four existing sub-agent tools directly. This makes the model chain internal implementation steps and increases routing complexity.

### 4. Treat partial source failures as structured workflow output

Workflows distinguish required and optional sources. Required source failures produce a clear workflow failure for that request. Optional source failures are represented as warnings or source-level error entries when useful partial results are available.

Alternative considered: fail the entire workflow on any source error. That would discard useful partial context for market briefings.

### 5. Keep observability lightweight and local to workflow execution

Workflow execution should record the selected mode, workflow name, internal units used, latency, completion status, and failure category. Use existing logging/observability patterns first; do not introduce a new external dependency for this foundation change.

Alternative considered: build a full workflow tracing system. That belongs with a future separated agent runtime, not this foundation.

## Risks / Trade-offs

- Replacing `generate_market_insight` may require updating tests and prompts that assert the old tool name -> Mitigate with compatibility at the chat response schema level and explicit tests for market insight replacement behavior.
- Workflow mode introduces a second orchestration path -> Mitigate with disabled-by-default configuration, mode-specific tool sets, and no silent fallback.
- Existing internal agent functions have mismatched payload assumptions -> Mitigate by adding the workflow layer as the public contract and allowing internal consolidation during implementation.
- Partial source failures can be confusing if not represented clearly -> Mitigate with structured warnings/errors in workflow results.
- Removing low-level sub-agent tools from model-facing tool sets may reduce flexibility -> Mitigate by keeping internal units reusable behind intent-level workflows.

## Migration Plan

1. Add mode selection and disabled-by-default workflow configuration while preserving legacy default behavior.
2. Split tool definitions into curated legacy and workflow tool sets.
3. Add intent-level workflow contracts and dispatch handlers.
4. Move market insight intent handling to the market briefing workflow and remove `generate_market_insight` from approved model-facing tool sets.
5. Add guardrail handling for runtime limits, orchestration step limits, source failures, and observability records.
6. Update tests to cover legacy default behavior, workflow opt-in behavior, insight replacement, and workflow failure isolation.

Rollback strategy: keep the feature flag disabled to preserve legacy behavior. If workflow implementation causes issues after deployment, disable workflow mode and redeploy/reconfigure without changing the legacy request path.

## Open Questions

None for this foundation design. Future separated agent runtime design should be handled in a separate OpenSpec change when product needs justify async jobs, custom agents, role-specific memory, or independent agent permissions.
