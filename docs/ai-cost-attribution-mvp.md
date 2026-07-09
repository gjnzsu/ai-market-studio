# AI Cost Attribution MVP

This MVP adds business attribution for AI Market Studio without replacing the existing Kong, ai-gateway-service, AI SRE observability, Prometheus, or Grafana stack.

## Runtime Flow

1. `ai-market-studio-ui` sends `/api/chat` with optional `clientContext`.
2. `ai-market-studio` generates or preserves a request ID.
3. The backend sends OpenAI-compatible chat completions through the configured gateway path with:
   - `X-Request-ID`
   - `X-Consumer-Service`
   - `X-AI-Application-ID`
   - `X-AI-Project-ID`
   - `X-AI-Team-ID`
   - `X-AI-Use-Case`
   - `X-AI-Feature`
4. `ai-gateway-service` records token usage and cost with AI ownership labels from the propagated headers.
5. A companion business metric records low-cardinality attribution labels.

## Metric

The business attribution metric is:

```promql
business_metric_total{metric_name="ai_cost_attribution_requests_total"}
```

Labels:

- `service`
- `application`
- `project`
- `team`
- `use_case`
- `feature`
- `model`
- `status`
- `tool_used`

Raw user IDs, session IDs, conversation IDs, prompts, and currency pairs are not Prometheus labels.

## MVP Queries

The Grafana dashboard is provisioned as:

- Standalone import JSON: `C:\SourceCode\ai-sre-observability\grafana\ai-market-studio-cost-attribution.json`
- Kubernetes ConfigMap entry: `C:\SourceCode\ai-sre-observability\k8s\grafana\grafana-dashboard.yaml`

Requests by use case over 24 hours:

```promql
sum(increase(business_metric_total{metric_name="ai_cost_attribution_requests_total"}[24h])) by (use_case)
```

Requests by feature and model:

```promql
sum(increase(business_metric_total{metric_name="ai_cost_attribution_requests_total"}[24h])) by (feature, model)
```

AI Market Studio token cost by model over 24 hours:

```promql
sum(increase(llm_token_cost_usd_total{service="ai-gateway-service", consumer="ai-market-studio"}[24h])) by (model)
```

Duplicate source review by service, consumer, and model:

```promql
sum(rate(llm_token_cost_usd_total[5m])) by (service, consumer, model)
```

Use-case request trend:

```promql
sum(rate(business_metric_total{metric_name="ai_cost_attribution_requests_total"}[5m])) by (use_case)
```

## Cost Counting Guidance

Do not add `business_metric_total` to cost totals. It is a companion attribution counter, not a cost metric.

For MVP dashboards:

- Use `llm_token_cost_usd_total{service="ai-gateway-service", consumer="ai-market-studio"}` for AI Market Studio product cost.
- Use `llm_tokens_total{service="ai-gateway-service", consumer="ai-market-studio"}` for AI Market Studio token volume.
- Use `business_metric_total` for use-case and feature request attribution.
- Use technical cost/token panels grouped by `service`, `consumer`, and `model` to detect duplicate sources.
- Do not sum backend technical LLM metrics and gateway technical LLM metrics for an app-specific cost total.
- Join exact requests through `X-Request-ID` in logs or traces when exact per-request reconciliation is required.

## Dashboard Interpretation

Use these dashboard views for the MVP end-to-end check:

- `AI Market Studio - Cost Attribution` shows application-level business attribution. Cost panels use gateway-sourced LLM cost filtered with `service="ai-gateway-service"` and `consumer="ai-market-studio"`. Attribution panels use `business_metric_total{metric_name="ai_cost_attribution_requests_total"}`.
- `LLM Cost & Usage` shows platform-level provider and model usage. Provider/model charts intentionally aggregate application attribution labels so one model does not appear as multiple lines for each use case or consumer.
- `Service Overview - Health & Metrics` uses `Total LLM Requests (Last Hour)` for the top request stat. This is a count, not a per-second rate, so low-frequency AI calls do not round down to `0 req/s`.
- `Request Tracing & Performance` also uses `Total Requests (Last Hour)` for the top request stat. The lower status breakdown keeps `rate(llm_requests_total[5m])` for real-time traffic shape.

For low-volume MVP testing, prefer last-hour count panels for acceptance and use request-rate panels for trend and status breakdowns.
