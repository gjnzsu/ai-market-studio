## Context

The archived agent workflow foundation introduced explicit legacy/workflow modes and intent-level tools such as `collect_market_context`, `analyze_market_context`, and `generate_market_briefing`. The workflow path is intentionally opt-in and backward compatible, but its market briefing output is still generic.

The project now has a curated Codex plugin with four AI Market Studio financial skills: FX carry trade analysis, macro-rates monitor, FX morning note, and FX/macro catalyst calendar. Those skills are useful design material, but they are not runtime agent tools. Runtime behavior needs a small backend abstraction that distills the skills into source requirements, output sections, and data-gap discipline.

## Goals / Non-Goals

**Goals:**

- Add runtime playbooks that encode professional FX/macro analysis frames.
- Let workflow-mode briefing requests select a playbook by explicit parameter or inferred user intent.
- Keep results source-grounded by showing required sources, optional sources, selected playbook, and missing data gaps.
- Preserve the existing chat response shape: `reply`, `data`, and `tool_used`.
- Keep implementation small and testable inside the existing backend agent workflow layer.

**Non-Goals:**

- Do not load Codex `SKILL.md` files directly at application runtime.
- Do not add broker connectivity, order execution, portfolio trading, or investment recommendation automation.
- Do not add paid data connectors in the first version.
- Do not make workflow mode the default for existing clients.

## Decisions

### Use a playbook registry instead of embedding skill text in prompts

The backend will define a compact registry of playbook definitions, each with an identifier, trigger terms, required sources, optional sources, output sections, and data-gap rules.

Alternatives considered:
- Full `SKILL.md` prompt injection: rejected because it increases latency/cost and mixes developer guidance with end-user runtime behavior.
- Separate model-facing tools per playbook: deferred because the existing `generate_market_briefing` workflow can carry the first version with less tool-selection complexity.

### Add optional `playbook` selection to market briefing

`generate_market_briefing` will accept an optional `playbook` argument. If omitted, the workflow will infer a playbook from the request focus/pairs and fall back to a general market briefing.

Alternatives considered:
- Force every workflow request to specify a playbook: rejected because it would be brittle for natural-language chat.
- Only infer from prompt text without schema support: rejected because explicit selection is useful for tests, UI controls, and future saved briefing profiles.

### Represent missing data explicitly

Playbook results will include `data_gaps`, such as missing forward curves, implied volatility, central-bank calendars, or richer macro indicators. Missing optional sources must not fail the workflow; missing required sources follows existing guardrail behavior.

Alternatives considered:
- Hide missing inputs from the user: rejected because professional financial analysis should distinguish observed data from inference.
- Fail all playbooks when optional specialist data is missing: rejected because the current MVP data surface is intentionally limited.

### Keep playbooks deterministic and model-light

The playbook layer will structure and label results. It will not make a second LLM call or generate freeform advice itself. The existing agent loop can use the structured result summary to produce the final conversational response.

Alternatives considered:
- Add a second summarization LLM call in the workflow: deferred until the value is proven, because it increases cost and makes tests less deterministic.

## Risks / Trade-offs

- Over-specialized playbook selection can choose the wrong frame -> Keep explicit `playbook` override and conservative fallback to general briefing.
- Users may read research framing as trading advice -> Include research-only language in playbook outputs and avoid execution instructions.
- Current data sources are incomplete for true carry/volatility analysis -> Add clear `data_gaps` and confidence labels.
- More structured output can make frontend rendering more complex -> Preserve existing response shape and place playbook details inside `data`.

## Migration Plan

1. Add playbook registry and unit tests.
2. Extend workflow tool schema and dispatch path with optional `playbook`.
3. Extend `generate_market_briefing` output with playbook metadata and data gaps.
4. Add agent/tool tests proving explicit and inferred playbook selection.
5. Keep workflow mode gated by existing configuration.

Rollback is simple: remove the optional playbook field and registry use while preserving the existing generic briefing path.

## Open Questions

- Should future UI expose playbook selection as a saved briefing profile, a dropdown, or purely natural-language selection?
- Which richer data provider should supply forward curves and volatility if FX carry analysis becomes a first-class product surface?
