## 1. Playbook Registry

- [x] 1.1 Add unit tests for the financial analysis playbook registry and initial playbook definitions.
- [x] 1.2 Implement the runtime playbook registry with FX carry, macro-rates, morning-note, catalyst-calendar, and general briefing playbooks.
- [x] 1.3 Add tests for explicit playbook lookup, intent inference from focus text, and fallback to general briefing.
- [x] 1.4 Implement playbook selection helpers used by workflows.

## 2. Workflow Tool Contract

- [x] 2.1 Add tool schema tests proving `generate_market_briefing` accepts an optional `playbook` field.
- [x] 2.2 Update the workflow tool definition and dispatch path to pass the optional playbook identifier.
- [x] 2.3 Add dispatch tests proving explicit playbook selection reaches the market briefing workflow.

## 3. Market Briefing Output

- [x] 3.1 Add workflow tests proving selected playbook metadata appears in `generate_market_briefing` results.
- [x] 3.2 Add workflow tests proving optional unavailable specialist data is represented as `data_gaps`.
- [x] 3.3 Extend `generate_market_briefing` results with selected playbook, source grounding, output sections, and data gaps.
- [x] 3.4 Add tests proving FX carry playbook output remains research-only and does not include execution instructions.

## 4. Agent Integration

- [x] 4.1 Add agent tests proving workflow mode can call `generate_market_briefing` with an explicit playbook.
- [x] 4.2 Add agent tests proving playbook details are preserved inside the chat response `data` shape.
- [x] 4.3 Update compact tool-result summarization to include playbook and data-gap details for final LLM responses.

## 5. Verification and Documentation

- [x] 5.1 Run targeted unit and agent tests for playbooks, tools, workflows, and chat response behavior.
- [x] 5.2 Run strict OpenSpec validation for `productize-financial-analysis-playbooks`.
- [x] 5.3 Update README or developer documentation with the new runtime playbook behavior and non-goals.
