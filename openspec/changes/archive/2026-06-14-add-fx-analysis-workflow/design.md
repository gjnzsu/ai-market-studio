## Context

`consolidate-agent-runtime` makes the workflow/playbook runtime the single chat runtime. After that consolidation, `analyze_market_context` is the natural entry point for a first-version FX analysis agent.

Today, `analyze_market_context` delegates to `analyze_market_trends` and returns a generic `market_analysis` result. That is useful but too thin for an FX analyst experience: it does not clearly separate market context, technical signals, macro/news/research drivers, scenarios, data gaps, and research-only framing.

This change introduces a workflow-first FX analysis capability. It deliberately avoids autonomy mode. The goal is a reliable baseline that later autonomy experiments can be compared against.

## Goals / Non-Goals

**Goals:**

- Return a stable `fx_analysis` payload for FX pair analysis requests.
- Keep the model-facing tool surface unchanged.
- Ground analysis in collected or supplied market context.
- Include data gaps when optional sources are missing.
- Include research-only framing and avoid execution advice.
- Support one or more pairs, with a clear primary pair when multiple pairs are present.
- Support a simple analysis horizon such as `intraday`, `1w`, `1m`, or `3m`.
- Provide a baseline output suitable for UI rendering, PDF export, and later evaluation against autonomy mode.

**Non-Goals:**

- Do not add autonomous planning.
- Do not add a new `/api/chat` mode.
- Do not expose raw connector tools to the model.
- Do not add live execution, order routing, or broker-specific advice.
- Do not require live derivatives data such as forward curves, options surfaces, or positioning feeds.
- Do not replace the existing briefing/playbook path; full narrative reports still use `generate_market_briefing`.

## Decisions

### Extend `analyze_market_context` rather than add a new model-facing tool

The first version should keep the approved tool surface stable. FX analysis is a type of market analysis, so `analyze_market_context` should own it.

Alternatives considered:

- Add `generate_fx_analysis` as a fourth model-facing tool. This may become useful later, but it increases tool-selection surface before the core analysis contract is proven.
- Build the feature only as a playbook. Playbooks are good for reports, but users also need direct analysis without a full briefing.

### Add an internal FX analysis builder

Implementation should use a focused internal function, for example `build_fx_analysis`, called by `analyze_market_context` when the request is FX pair analysis. It can live in `backend/agent/workflows.py` initially or a new internal specialist module if the implementation grows.

The function should accept normalized context and return deterministic structured sections. This keeps tests simple and avoids hiding analysis behavior inside prompts.

### Use deterministic first-version analytics

First-version calculations should be lightweight:

- trend direction and momentum from available rate observations
- volatility snapshot from available rate observations
- source availability and data gaps
- driver summaries from news, FRED, and research context when available
- simple scenario scaffolding, not prediction claims
- confidence derived from data availability and analysis completeness

When rate history is unavailable and only a spot rate exists, the workflow should return a valid analysis with explicit insufficient-history gaps.

### Keep LLM role bounded

The LLM can select `analyze_market_context`, choose parameters, and write the final explanation from the structured result. It should not invent missing drivers or convert the result into execution advice.

### Preserve briefing path

If the user asks for a morning note, carry view, macro monitor, or full briefing, `generate_market_briefing` remains the appropriate workflow. The new `fx_analysis` payload should be usable by briefing internals later, but this change does not require briefing rewrites.

## Risks / Trade-offs

- [Risk] First-version analysis may feel formulaic. -> Mitigation: prioritize stable structure first; improve narratives and analytics after baseline tests exist.
- [Risk] Spot-only context may produce weak trend/volatility output. -> Mitigation: include explicit data gaps and confidence penalties.
- [Risk] Adding too many output fields can make UI integration harder. -> Mitigation: define a compact required core and optional sections.
- [Risk] Users may interpret scenarios as trade recommendations. -> Mitigation: label output as research-only and avoid buy/sell/order language.
- [Risk] Autonomy experiments later may need a different trace shape. -> Mitigation: keep this workflow as baseline output, not as the autonomy trace format.

## Migration Plan

1. Add tests for the `fx_analysis` payload contract.
2. Extend the `analyze_market_context` tool schema with optional `horizon` and `focus` parameters.
3. Add an internal FX analysis builder and route FX analysis requests through it.
4. Preserve existing `market_analysis` behavior only where necessary for non-FX or legacy tests, or migrate those tests to the new FX-specific result.
5. Update README with the FX analysis workflow example.
6. Validate OpenSpec and targeted unit/agent/e2e tests.

## Open Questions

- Should `fx_analysis` become the default result for all pair-based `analyze_market_context` calls, or only when `analysis_type` is `general`, `trend`, or an explicit `fx_analysis` value?
- Should first-version historical rates be collected by `collect_market_context` when `days` is provided, or should spot-only analysis remain the initial scope?
- Should the output include numeric confidence as a float, a qualitative label, or both?
