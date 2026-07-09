## 1. Backend Attribution Contract

- [x] 1.1 Add optional chat cost attribution request models with safe defaults and backward compatibility.
- [x] 1.2 Add deterministic use case and feature classification helpers for the three MVP AI entry points.

## 2. Gateway Correlation

- [x] 2.1 Generate or preserve a stable request ID for each `/api/chat` execution.
- [x] 2.2 Propagate request ID and low-cardinality attribution headers to the OpenAI-compatible gateway client.

## 3. Observability Metrics

- [x] 3.1 Emit a low-cardinality business attribution metric through the existing observability SDK.
- [x] 3.2 Ensure observability failures degrade gracefully without failing chat execution.

## 4. UI, Tests, and Documentation

- [x] 4.1 Update the static UI chat payload to send minimal `client_context` for AI Market Studio.
- [x] 4.2 Add or update backend tests for request compatibility, fallback classification, and header propagation.
- [x] 4.3 Document MVP Prometheus/Grafana queries and the double-counting guidance.
- [x] 4.4 Run the AI app quality gate.

## 5. Cost Attribution Dashboard

- [x] 5.1 Add a Grafana dashboard for AI Market Studio cost attribution.
- [x] 5.2 Provision the dashboard through the existing Kubernetes Grafana dashboard ConfigMap.
- [x] 5.3 Add dashboard validation tests for key business attribution and cost PromQL queries.
- [x] 5.4 Run the AI app quality gate after dashboard provisioning.

## 6. QA Defect Fixes

- [x] 6.1 Add gateway LLM metric ownership labels for consumer, application, project, team, use case, and feature.
- [x] 6.2 Update AI Market Studio cost dashboard queries to use gateway cost filtered by consumer instead of summing backend plus gateway cost.
- [x] 6.3 Fix standalone Grafana dashboard metric names to use `llm_token_cost_usd_total`.
- [x] 6.4 Add duplicate-source review panels and tests that guard against app-specific double-counting.
- [x] 6.5 Run the AI app quality gate after defect fixes.
