## Context

The current chat agent has two runtimes. The default `legacy` runtime exposes low-level tools such as spot rates, news, FRED, dashboards, and correlation directly to the model. The opt-in `workflow` runtime exposes intent-level tools: `collect_market_context`, `analyze_market_context`, and `generate_market_briefing`.

Recent playbook work and README guidance already point to workflow mode as the product direction, but the code still preserves mode selection, a workflow enablement gate, legacy system prompts, legacy tool definitions, and tests for both paths. The result is a confusing architecture for future FX analysis work: the product wants workflow/playbook behavior, while the implementation still treats legacy as the default.

## Goals / Non-Goals

**Goals:**

- Make `/api/chat` use one workflow-based agent runtime.
- Remove `agent_mode` from the chat request contract.
- Remove the workflow enablement gate and legacy fallback behavior.
- Make intent-level workflow tools the only model-facing tools.
- Preserve the existing top-level chat response shape: `reply`, `data`, and `tool_used`.
- Keep connector-backed FX, news, FRED, research, and analysis capabilities available through workflow internals.
- Clarify that low-level "sub-agent" functions are internal specialists or services, not model-facing tools.
- Prepare the codebase for a future FX analysis capability built on `analyze_market_context` and playbooks.

**Non-Goals:**

- Add a new FX analysis playbook in this change.
- Redesign the frontend chat UI.
- Remove connector implementations.
- Change PDF export, dashboard endpoints, or non-chat APIs unless they directly depend on chat agent mode.
- Add live trading execution advice or order-routing behavior.

## Decisions

### Use workflow runtime as the only chat runtime

`run_agent` will no longer accept or branch on `agent_mode`. It will always use the workflow system prompt, workflow tool definitions, and workflow max-round policy.

Alternatives considered:

- Keep both modes and default to workflow. This preserves confusion and leaves dead paths for new work to accidentally extend.
- Delete workflow and keep legacy. This contradicts the playbook architecture and would make FX analysis harder to structure.

### Remove `agent_mode` from `/api/chat`

`ChatRequest` will contain `message` and `history` only. Requests that include `agent_mode` should be rejected by Pydantic rather than silently ignored, so clients see that the contract changed.

Alternatives considered:

- Accept and ignore `agent_mode`. This is gentler but keeps the old mental model alive and can hide stale clients.
- Keep `agent_mode` only in docs. This would conflict with the runtime contract.

### Keep low-level capabilities internal

Low-level connector calls remain available through `collect_market_context`, `analyze_market_context`, and `generate_market_briefing`. The model-facing tool registry should not include `get_exchange_rate`, `get_fx_news`, `get_interest_rate`, `analyze_fx_economic_correlation`, `collect_market_data`, `generate_report`, or `synthesize_research`.

Internal modules under `backend/agents` should either be reused by workflows, renamed later to a less misleading location, or removed if they are not used. The first implementation pass should avoid large file moves unless tests show they are safe and valuable.

Alternatives considered:

- Keep low-level dispatch branches for manual/internal calls. This leaves unreachable but valid-looking behavior in `tools.py`.
- Expose both low-level and workflow tools to the model. This increases tool-selection ambiguity and undermines the intent-level design.

### Preserve response shape

The top-level chat response remains `reply`, `data`, and `tool_used`. The breaking change is request-mode removal, not response shape removal. Workflow-specific details continue to live inside `data`.

### Rename only active runtime config

`ENABLE_AGENT_WORKFLOW_MODE` should be removed. Existing timeout and max-round values may be retained with neutral names such as `AGENT_TIMEOUT_SECONDS` and `AGENT_MAX_ROUNDS`, or kept internally if a broader config rename would create unnecessary churn. Documentation must not describe workflow as an opt-in feature.

## Risks / Trade-offs

- Stale clients still sending `agent_mode` may fail validation. Mitigation: mark the change as breaking and update README/API examples.
- Removing low-level model-facing tools may reduce simple spot-rate answer quality if workflows do not cover those intents well. Mitigation: ensure `collect_market_context` handles simple data-only requests and add tests for simple rate/news/research requests.
- Existing tests encode legacy behavior. Mitigation: rewrite tests around the single runtime instead of deleting coverage wholesale.
- `backend/agents` naming may remain slightly confusing if file moves are deferred. Mitigation: remove model-facing dispatch references now and document internal-only usage; optionally rename in a follow-up cleanup.
- Workflow-only runtime may expose gaps in `generate_market_briefing` or `analyze_market_context`. Mitigation: keep the first pass focused on parity for currently supported workflow behavior, then improve FX analysis in a separate change.

## Migration Plan

1. Update schemas and router so `/api/chat` no longer accepts `agent_mode` and no longer checks workflow enablement.
2. Simplify `run_agent` to a single runtime prompt, tool set, and round limit.
3. Simplify `tools.py` so the model-facing tool definitions are workflow-only.
4. Remove unreachable legacy dispatch branches or move needed behavior behind workflow internals.
5. Update tests for request schema, router behavior, agent tool selection, and workflow dispatch.
6. Update README and architecture docs to remove legacy/workflow mode selection language.

Rollback is a git revert of this change. There is no data migration.
