## Why

AI Market Studio now has an opt-in agent workflow foundation, but the workflow still behaves like a generic market briefing layer. The next product step is to turn the financial analysis expertise captured in the project-specific Codex skills into runtime playbooks that make workflow-mode briefings feel more professional, source-grounded, and trader-relevant.

## What Changes

- Add a runtime financial analysis playbook registry for workflow-mode market analysis.
- Introduce four initial playbooks: FX carry, macro-rates monitor, FX morning note, and FX/macro catalyst calendar.
- Let workflow-mode market briefings select a playbook from user intent or explicit request parameters.
- Add structured playbook metadata to workflow results, including selected playbook, required sources, optional sources, output sections, source grounding, and data gaps.
- Keep legacy mode and existing `/api/chat` response shape backward compatible.
- Do not add live trade execution, broker connectivity, or investment-advice automation.

## Capabilities

### New Capabilities

- `financial-analysis-playbooks`: Runtime playbooks for professional FX and macro analysis framing in agent workflow mode.

### Modified Capabilities

- `intent-level-agent-workflows`: Market briefing workflows can select and apply a financial analysis playbook while preserving the existing structured response contract.

## Impact

- Affected code: `backend/agent/workflows.py`, `backend/agent/tools.py`, `backend/agent/agent.py`, and focused workflow/tool tests.
- Affected APIs: `/api/chat` remains backward compatible; workflow tool schemas may accept an optional playbook field.
- Affected data sources: existing FX connector, FRED connector, news connector, and RAG connector.
- Dependencies: no new external data provider or paid connector is required in the first version.
