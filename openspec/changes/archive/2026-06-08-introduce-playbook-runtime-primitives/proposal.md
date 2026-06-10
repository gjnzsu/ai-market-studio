## Why

Financial analysis playbooks are now useful enough to become a reusable product capability, but their runtime shape is still mostly a hardcoded registry plus workflow-specific enrichment logic. Introducing lightweight playbook runtime primitives will make new playbooks easier to add, keep demo/test behavior deterministic, and preserve the research-only boundary as the system grows.

## What Changes

- Introduce a backend-only runtime primitive model for financial analysis playbooks.
- Represent playbooks through structured definitions for identity, source contracts, output contracts, runtime profiles, and rules.
- Keep the existing playbook IDs and `/api/chat` workflow response contract stable.
- Move FX carry synthetic demo behavior toward explicit runtime profile/rule metadata rather than workflow-only special casing.
- Preserve deterministic demo/test behavior for synthetic specialist data and carry metrics.
- Keep external YAML/JSON configuration, UI editing, prompt template engines, and live trading/execution workflows out of scope.

## Capabilities

### New Capabilities
- `playbook-runtime-primitives`: Defines the runtime primitive layer used to compose, select, and explain backend financial analysis playbooks.

### Modified Capabilities
- `financial-analysis-playbooks`: Existing financial analysis playbooks are represented through runtime primitives while preserving current playbook behavior and response contracts.

## Impact

- Affected backend modules: `backend/agent/financial_playbooks.py`, `backend/agent/workflows.py`, and related playbook tests.
- Affected OpenSpec specs: add `playbook-runtime-primitives` and update `financial-analysis-playbooks`.
- Affected documentation: README and architecture/design notes should describe runtime primitives once implemented.
- No breaking API changes are expected for `/api/chat` or existing workflow-mode market briefing responses.
