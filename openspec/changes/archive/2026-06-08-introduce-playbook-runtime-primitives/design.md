## Context

AI Market Studio already supports workflow-mode market briefings with financial analysis playbooks for `general`, `fx_carry`, `macro_rates`, `morning_note`, and `catalyst_calendar`. Today those playbooks are represented by a compact `FinancialAnalysisPlaybook` dataclass, while FX carry synthetic specialist data and carry metrics are handled directly inside the market briefing workflow.

That shape is still acceptable for a small registry, but it makes the next playbook harder to add because definition, source contract, output contract, runtime profile, data-gap behavior, and synthetic disclosure are not clearly separated. The next step is not a full configuration engine; it is a lightweight backend runtime primitive layer that makes the existing behavior easier to extend and test.

## Goals / Non-Goals

**Goals:**
- Represent playbooks as structured runtime definitions composed from identity, source contract, output contract, runtime profiles, and rules.
- Preserve existing playbook IDs, selection behavior, and `/api/chat` response contract.
- Keep FX carry synthetic specialist data explicit, deterministic, and clearly disclosed as demo support.
- Make it easier to add a new playbook by changing playbook definitions and focused runtime handlers instead of editing broad workflow logic.
- Add tests around primitive composition, selection, source grounding, synthetic disclosure, and backward-compatible response shape.

**Non-Goals:**
- No UI playbook editor.
- No external YAML or JSON playbook loading in the first version.
- No prompt template engine.
- No live trading, execution advice, broker routing, or order workflow support.
- No breaking change to workflow mode configuration or chat request/response schemas.

## Decisions

### Keep primitives backend-only in the first version

Use Python definitions rather than YAML/JSON configuration. This keeps validation, test fixtures, type checking, and migration risk small while the primitive vocabulary is still settling.

Alternatives considered:
- YAML/JSON runtime config: better future configurability, but it adds schema validation, config errors, and deployment questions too early.
- Full primitive engine: flexible, but too much framework before we have enough playbook variety.

### Split the playbook model into focused primitive types

Introduce focused types such as:
- `PlaybookIdentity`: id, display name, intent triggers.
- `SourceContract`: required sources, optional sources, gap sources.
- `OutputContract`: expected output sections.
- `RuntimeProfile`: research-only and demo/synthetic behavior flags.
- `PlaybookRule`: small named rule metadata for source grounding, data-gap reporting, synthetic disclosure, and no-execution framing.
- `PlaybookDefinition`: composed runtime definition exposed to workflows.

The implementation does not need a rule interpreter in v1. Rules can be metadata plus small helper functions that the workflow uses to produce the same result shape more deliberately.

### Preserve current workflow output shape

`generate_market_briefing` should continue returning `playbook`, `source_grounding`, `data_gaps`, `specialist_data`, and `carry_metrics` in their current compatible form. New primitive metadata can be used internally and, if helpful, surfaced through additive fields only.

### Move FX carry synthetic behavior behind a profile-oriented helper

The FX carry synthetic layer should remain deterministic, but the workflow should ask the selected playbook/runtime layer whether a synthetic profile applies instead of owning all of that decision inline. This keeps demo metrics available while making future specialist-data profiles easier to add.

## Risks / Trade-offs

- Primitive vocabulary may still evolve after the next one or two playbooks -> Keep the first version code-defined and additive rather than external-config-driven.
- Adding rule metadata without a full interpreter may feel incomplete -> Treat rules as named contracts and testable helper behavior, not as a generic engine.
- Over-abstracting a small registry could reduce readability -> Keep primitive classes compact and use the existing five playbooks as acceptance examples.
- Response compatibility could regress while reshaping internals -> Add tests that compare current selected playbook metadata, source grounding, data gaps, and FX carry synthetic fields.

## Migration Plan

1. Add runtime primitive types and a registry module.
2. Migrate the existing playbook definitions to the new composed model.
3. Keep compatibility helpers such as `list_playbooks`, `get_playbook`, and `select_playbook`.
4. Refactor workflow code to consume the runtime definition and profile helpers.
5. Run existing unit/e2e tests and add focused tests for primitive behavior.

Rollback is straightforward because the change is backend-only and additive: restore the previous compact playbook registry and workflow inline logic if compatibility tests fail.

## Open Questions

- Should additive response metadata expose runtime profile IDs in v1, or should profile/rule information remain internal until the UI needs it?
- Should a future v2 load playbooks from a versioned configuration file, or keep Python definitions until a UI editor exists?
