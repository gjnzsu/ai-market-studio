## 1. Runtime Primitive Model

- [x] 1.1 Add compact backend primitive types for playbook identity, source contract, output contract, runtime profile, rule metadata, and composed playbook definition.
- [x] 1.2 Add registry helpers that list, fetch, and select runtime playbook definitions by explicit ID or inferred focus text.
- [x] 1.3 Preserve compatibility helpers or adapters for existing callers that expect current playbook metadata fields.

## 2. Existing Playbook Migration

- [x] 2.1 Migrate `general`, `fx_carry`, `macro_rates`, `morning_note`, and `catalyst_calendar` into composed runtime definitions.
- [x] 2.2 Represent research-only behavior and source-grounding behavior as runtime rule metadata.
- [x] 2.3 Represent FX carry synthetic specialist data behavior as a runtime profile rather than workflow-only special casing.

## 3. Workflow Integration

- [x] 3.1 Refactor `generate_market_briefing` to consume runtime playbook definitions without changing the `/api/chat` response contract.
- [x] 3.2 Move FX carry synthetic specialist data decision-making behind runtime profile/helper logic while preserving deterministic outputs.
- [x] 3.3 Ensure source grounding still reports requested sources, connector-backed available sources, synthetic sources, missing required sources, and missing optional sources.
- [x] 3.4 Ensure playbook outputs continue to frame results as research-only briefing support.

## 4. Tests and Verification

- [x] 4.1 Add unit tests for primitive composition and runtime registry selection.
- [x] 4.2 Update existing financial playbook and workflow tests to assert backward-compatible metadata and response shape.
- [x] 4.3 Add or update FX carry tests for synthetic profile behavior, deterministic specialist data, carry metrics, and data-gap suppression.
- [x] 4.4 Run focused backend tests covering playbooks, workflows, tools, and agent response summarization.
- [x] 4.5 Run OpenSpec validation for the change.

## 5. Documentation

- [x] 5.1 Update README playbook documentation to explain runtime primitives at a product level.
- [x] 5.2 Update architecture/design notes if the runtime primitive layer changes the component or workflow diagram story.
