## 1. Synthetic Specialist Data

- [x] 1.1 Add unit tests for deterministic synthetic forward curve data for supported FX pairs.
- [x] 1.2 Add unit tests for deterministic synthetic implied volatility data for supported FX pairs.
- [x] 1.3 Implement a small synthetic specialist data helper/provider for forward curve and implied volatility outputs with explicit `source: synthetic` provenance.

## 2. FX Carry Metrics

- [x] 2.1 Add unit tests for lightweight FX carry metric calculation using spot context, FRED context when present, and synthetic specialist data.
- [x] 2.2 Implement deterministic carry metrics including rate differential proxy, forward premium or discount, and carry-to-vol indicator.
- [x] 2.3 Ensure metric naming and interpretations are research/demo oriented and do not include execution instructions.

## 3. Workflow Integration

- [x] 3.1 Add workflow tests proving FX carry briefings include synthetic forward curve, synthetic implied volatility, and carry metrics.
- [x] 3.2 Add workflow tests proving synthetic sources are represented separately from connector-backed available sources.
- [x] 3.3 Add workflow tests proving forward curve and implied volatility are not reported as unavailable data gaps when synthetic data is used.
- [x] 3.4 Integrate the synthetic specialist data and carry metrics into `generate_market_briefing` for the FX carry playbook.

## 4. Guardrails and Regression Coverage

- [x] 4.1 Add or update tests proving FX carry outputs remain research-only when synthetic metrics are present.
- [x] 4.2 Run focused unit tests for financial playbooks, workflows, and synthetic specialist data.
- [x] 4.3 Run OpenSpec validation for `enhance-fx-carry-playbook-demo-metrics`.

## 5. Documentation

- [x] 5.1 Update README or relevant project documentation to explain synthetic specialist data boundaries and demo-only provenance.
