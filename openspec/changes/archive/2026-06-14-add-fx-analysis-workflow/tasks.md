## 1. Contract Tests

- [x] 1.1 Add workflow tests for single-pair `fx_analysis` result shape.
- [x] 1.2 Add workflow tests for multi-pair FX analysis labeling.
- [x] 1.3 Add workflow tests for source grounding, data gaps, confidence, and research-only framing.
- [x] 1.4 Add tool schema tests for optional `horizon` and `focus` parameters on `analyze_market_context`.

## 2. Internal FX Analysis Builder

- [x] 2.1 Add an internal FX analysis builder that accepts market context, pairs, horizon, focus, and analysis type.
- [x] 2.2 Implement trend, momentum, and volatility sections from available rate observations.
- [x] 2.3 Implement drivers, scenarios, watch items, limitations, and data gaps.
- [x] 2.4 Implement confidence scoring based on available sources and analysis completeness.
- [x] 2.5 Preserve research-only framing and avoid execution advice.

## 3. Workflow Integration

- [x] 3.1 Extend `analyze_market_context` parameters to accept `horizon` and `focus`.
- [x] 3.2 Route FX pair analysis requests to the internal FX analysis builder.
- [x] 3.3 Preserve existing market analysis behavior for non-FX or unsupported contexts where needed.
- [x] 3.4 Ensure compact pair notation such as `EURUSD` is normalized consistently.

## 4. Agent and API Tests

- [x] 4.1 Update agent-loop tests proving the model can call `analyze_market_context` for FX analysis.
- [x] 4.2 Add or update chat API/e2e tests for an FX analysis request returning workflow data.
- [x] 4.3 Verify RAG/news/FRED optional source gaps do not break FX analysis.

## 5. Documentation

- [x] 5.1 Document the first-version FX analysis workflow in README.
- [x] 5.2 Clarify that autonomy mode is out of scope and this workflow is the baseline for future comparison.

## 6. Verification

- [x] 6.1 Run targeted unit tests for tools, workflows, and agent loop.
- [x] 6.2 Run targeted chat API/e2e tests.
- [x] 6.3 Run OpenSpec validation for `add-fx-analysis-workflow`.
