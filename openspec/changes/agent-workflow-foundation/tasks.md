## 1. Mode Selection Foundation

- [x] 1.1 Add a disabled-by-default configuration setting for agent workflow availability.
- [x] 1.2 Extend the chat request model with an optional orchestration mode field that defaults to legacy behavior when omitted.
- [x] 1.3 Update the chat route to reject workflow mode with a clear client-facing error when workflow mode is disabled.
- [x] 1.4 Pass the selected orchestration mode from the chat route into the agent runtime.
- [x] 1.5 Add tests proving existing chat requests without a mode still use legacy orchestration and keep the existing response shape.

## 2. Mode-Specific Tool Sets

- [x] 2.1 Split the current global tool definitions into explicit legacy and workflow tool definition groups.
- [x] 2.2 Remove `generate_market_insight` from approved model-facing tool sets.
- [x] 2.3 Remove low-level internal agent tools from workflow-mode model-facing tool exposure.
- [x] 2.4 Add workflow-mode tool definitions for market context collection, market context analysis, and market briefing.
- [x] 2.5 Update the agent runtime to send the tool set that matches the selected orchestration mode.
- [x] 2.6 Add tests proving legacy mode does not expose workflow tools and workflow mode does not expose low-level internal agent tools.

## 3. Intent-Level Workflow Layer

- [ ] 3.1 Create workflow implementation units for `collect_market_context`, `analyze_market_context`, and `generate_market_briefing`.
- [ ] 3.2 Implement market context collection so it collects requested market context without running analysis or synthesis.
- [ ] 3.3 Implement market context analysis so it returns analysis grounded in collected or supplied context without generating a full briefing.
- [ ] 3.4 Implement market briefing so market insight, overview, briefing, and multi-source synthesis intents use the new workflow path.
- [ ] 3.5 Reuse, narrow, or consolidate existing `backend/agents/*` internals behind the workflow layer where their current boundaries overlap.
- [ ] 3.6 Add tests for data-only workflow behavior, analysis-only workflow behavior, and briefing workflow behavior.

## 4. Market Insight Replacement

- [ ] 4.1 Route market insight, overview, briefing, and synthesis intents to the market briefing workflow in workflow mode.
- [ ] 4.2 Remove or deprecate dispatch support for the legacy `generate_market_insight` tool so it is no longer an approved model-facing tool.
- [ ] 4.3 Update tests that assert old market insight tool behavior to assert the new market briefing workflow behavior.
- [ ] 4.4 Verify existing chat clients still receive compatible `reply`, `data`, and `tool_used` response fields for market insight requests.

## 5. Workflow Guardrails

- [ ] 5.1 Enforce a runtime limit for workflow-mode requests.
- [ ] 5.2 Enforce a bounded orchestration step limit for workflow-mode requests.
- [ ] 5.3 Return clear workflow timeout and workflow failure responses without silently falling back to legacy orchestration.
- [ ] 5.4 Represent optional source failures as structured workflow warnings or source-level errors when useful partial results are available.
- [ ] 5.5 Return clear failures for missing required sources without presenting missing required data as successful context.
- [ ] 5.6 Add tests for workflow timeout, step limit, no-silent-fallback behavior, optional source failure, and required source failure.

## 6. Observability and Regression Coverage

- [ ] 6.1 Add workflow execution logs or metrics for selected mode, workflow name, internal units used, latency, status, and failure category.
- [ ] 6.2 Add regression tests proving workflow failures do not alter later legacy-mode requests.
- [ ] 6.3 Run the targeted agent, tool, and chat test suites.
- [ ] 6.4 Run OpenSpec validation for `agent-workflow-foundation`.
- [ ] 6.5 Update README or developer docs if the new mode setting or workflow tools need local usage guidance.
