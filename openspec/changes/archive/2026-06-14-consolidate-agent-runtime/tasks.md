## 1. Contract and Router

- [x] 1.1 Update `ChatRequest` so `/api/chat` accepts `message` and optional `history` only, and rejects unknown `agent_mode` input.
- [x] 1.2 Remove workflow-mode enablement checks from `/api/chat`.
- [x] 1.3 Replace mode-specific timeout selection with a single chat agent timeout policy.
- [x] 1.4 Update schema and chat API tests for the single runtime request contract.

## 2. Agent Runtime

- [x] 2.1 Simplify `run_agent` to remove the `agent_mode` parameter and all legacy/workflow branching.
- [x] 2.2 Replace dual system prompts with one workflow-oriented system prompt.
- [x] 2.3 Use one max-round setting for the chat agent runtime.
- [x] 2.4 Update agent-loop tests to assert the workflow tool set is always used.

## 3. Tool Registry and Dispatch

- [x] 3.1 Make the model-facing chat tool definitions contain only `collect_market_context`, `analyze_market_context`, and `generate_market_briefing`.
- [x] 3.2 Remove legacy model-facing tool aliases and tests for `LEGACY_TOOL_DEFINITIONS`, `WORKFLOW_TOOL_DEFINITIONS`, and mode-based `get_tool_definitions`.
- [x] 3.3 Remove or quarantine unreachable dispatch branches for legacy connector tools and legacy sub-agent tools.
- [x] 3.4 Preserve workflow dispatch branches for `collect_market_context`, `analyze_market_context`, and `generate_market_briefing`.
- [x] 3.5 Add tests proving low-level connector tools and legacy sub-agent tools are not in the model-facing chat tool set.

## 4. Internal Workflow Coverage

- [x] 4.1 Ensure `collect_market_context` covers simple spot-rate, news, FRED, and research collection use cases that legacy tools previously served.
- [x] 4.2 Ensure `analyze_market_context` still reuses the internal market analysis specialist where appropriate.
- [x] 4.3 Ensure `generate_market_briefing` still returns playbook metadata, source grounding, warnings, synthetic specialist data, and carry metrics.
- [x] 4.4 Add or update tests for simple data-only requests, analysis requests, and market briefing requests through the single runtime.

## 5. Configuration and Documentation

- [x] 5.1 Remove `ENABLE_AGENT_WORKFLOW_MODE` from settings, README, and deployment docs.
- [x] 5.2 Rename or document remaining timeout/max-round settings as generic chat agent runtime settings.
- [x] 5.3 Update README examples to omit `agent_mode`.
- [x] 5.4 Update architecture docs to describe one workflow/playbook-based chat runtime and mark older multi-agent/legacy docs as superseded where appropriate.

## 6. Verification

- [x] 6.1 Run targeted unit tests for schemas, tools, workflows, and agent loop.
- [x] 6.2 Run targeted chat API tests.
- [x] 6.3 Run OpenSpec validation for `consolidate-agent-runtime`.
- [x] 6.4 Review remaining references to legacy mode, workflow opt-in, and model-facing sub-agent tools.
