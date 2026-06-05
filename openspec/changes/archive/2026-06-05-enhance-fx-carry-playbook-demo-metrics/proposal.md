## Why

The FX carry playbook currently frames the analysis well but stops at explicit gaps for forward curve and implied volatility inputs. Adding a synthetic specialist data layer lets the playbook demonstrate deterministic carry metrics for demos and tests while preserving clear non-live-market-data boundaries.

## What Changes

- Add deterministic synthetic specialist data for FX carry playbook demos, initially covering forward curve tenors and implied volatility tenors.
- Add lightweight FX carry metrics derived from real/mock spot context, FRED rate context when available, and synthetic specialist assumptions.
- Represent synthetic provenance separately from live or connector-backed data so users can distinguish real data, mock spot data, and synthetic specialist assumptions.
- Change FX carry source grounding so synthetic forward curve and implied volatility are not reported as unavailable when the synthetic layer is used.
- Preserve research-only wording and avoid trading execution instructions, order directives, or claims that synthetic values are live market quotes.

## Capabilities

### New Capabilities
- `synthetic-specialist-data`: Provides deterministic, clearly labeled synthetic specialist data for demo and test workflows.

### Modified Capabilities
- `financial-analysis-playbooks`: FX carry playbook can consume synthetic forward curve and implied volatility data to produce deterministic demo carry metrics while remaining research-only.

## Impact

- Backend workflow runtime for `generate_market_briefing`, especially FX carry playbook handling.
- New backend helper/provider code for synthetic forward curve, synthetic implied volatility, and carry metric calculation.
- Unit tests for deterministic synthetic outputs, provenance, source grounding, and research-only guardrails.
- Chat API structured response shape may gain additive fields such as `specialist_data`, `carry_metrics`, and synthetic source grounding metadata.
