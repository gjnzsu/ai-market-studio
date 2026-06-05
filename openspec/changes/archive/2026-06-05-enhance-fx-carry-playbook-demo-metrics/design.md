## Context

AI Market Studio already supports workflow-mode market briefings and runtime financial analysis playbooks. The FX carry playbook requires spot FX rates and FRED macro rates, and currently identifies forward curve and implied volatility as optional specialist data gaps because no connector supplies them.

This change adds a deterministic synthetic specialist data layer for FX carry demos and tests. The layer must make the playbook feel more complete without pretending to provide live derivatives market data.

## Goals / Non-Goals

**Goals:**
- Provide deterministic synthetic forward curve and implied volatility data for FX carry playbook runs.
- Calculate lightweight demo carry metrics from spot context, FRED context when present, and synthetic specialist assumptions.
- Preserve explicit provenance so users and downstream UI can distinguish connector-backed data from synthetic assumptions.
- Keep the FX carry briefing research-only and free of execution instructions.
- Keep the first implementation small enough to complete inside the existing backend workflow and test suite.

**Non-Goals:**
- Do not connect to live forward curve, swap, broker, options, or volatility data providers.
- Do not build trading recommendations, entry/exit levels, order routing, position sizing, or portfolio ranking.
- Do not generalize the synthetic layer to every playbook in the first version.
- Do not require UI charting for forward curves or volatility smiles in the first version.

## Decisions

### Keep synthetic specialist data separate from `MarketDataConnector`

Use a small backend helper/provider for synthetic FX specialist data instead of expanding the existing spot FX connector interface.

Rationale: `MarketDataConnector` currently represents spot and historical FX rates. Forward curves and implied volatility are specialist derivatives-style inputs with different semantics. Keeping them in a separate helper avoids making the connector abstraction too broad and clearly signals that this is a playbook support layer.

Alternative considered: add methods such as `get_forward_curve` and `get_implied_volatility` to `MarketDataConnector`. This was rejected for the MVP because it would force every connector implementation to handle data it does not own.

### Add synthetic provenance as structured data

Workflow results should expose synthetic data under an additive structure such as `specialist_data` and source grounding metadata such as `synthetic_sources`.

Rationale: The application already mixes real FRED data and mock spot FX data. Synthetic specialist assumptions need an explicit label so users do not confuse them with market quotes. A separate source class also gives the UI a clean display path.

Alternative considered: treat synthetic forward curve and implied volatility as ordinary `available_sources`. This is less clear because it collapses real connector-backed data and synthetic assumptions into the same bucket.

### Calculate only lightweight deterministic metrics

The FX carry playbook should calculate simple metrics such as rate differential proxy, forward premium/discount, and carry-to-vol ratio.

Rationale: Deterministic metrics are easy to test and useful for demos. They improve product feel without introducing model risk or pretending to be a full trading analytics engine.

Alternative considered: use more realistic valuation models. This was rejected for now because model details would imply a level of financial accuracy that the current synthetic data layer is not intended to provide.

### Enable synthetic data for FX carry playbook runs by default

When the FX carry playbook is selected, the workflow should use the synthetic specialist layer unless an implementation-level toggle later disables it.

Rationale: The product goal is to make the playbook complete and demonstrable. Clear provenance and research-only language are a better first-version control than a configuration flag that makes demos inconsistent.

Alternative considered: require an environment flag such as `ENABLE_SYNTHETIC_SPECIALIST_DATA`. This may be useful later, but it adds configuration complexity before there is a real production/live-data distinction for the specialist layer.

## Risks / Trade-offs

- Synthetic data may be mistaken for live data -> Mitigate with `source: synthetic`, explicit `synthetic_sources`, and briefing caveats.
- Metrics may look more authoritative than intended -> Mitigate with research-only language and conservative names such as `rate_differential_proxy`.
- Scope may expand into real trading analytics -> Mitigate by limiting MVP to FX carry, deterministic assumptions, and no execution outputs.
- UI may not yet render new fields elegantly -> Mitigate by making response fields additive and preserving existing briefing text and source grounding behavior.

## Migration Plan

The change is additive. Existing workflow callers continue to call `generate_market_briefing` with the same schema. FX carry responses gain extra structured fields and revised source grounding when synthetic specialist data is available.

Rollback can remove or disable the synthetic layer and restore the current behavior where forward curve and implied volatility appear in `data_gaps`.

## Open Questions

- Should a later version expose a request-level or environment-level toggle for synthetic specialist data?
- Should UI render synthetic forward curve and implied volatility as compact chips, mini tables, or charts in a follow-up change?
