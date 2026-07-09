## Why

AI Market Studio already routes LLM calls through Kong, ai-gateway-service, and the AI SRE observability stack, but current cost visibility is mostly technical: service, provider, model, tokens, latency, and status. The MVP needs business attribution so project owners can understand whether FX data queries, advisory reports, or conversational dashboard generation are driving token usage and cost.

## What Changes

- Add a cost attribution contract for AI Market Studio chat requests without breaking the existing `/api/chat` response shape.
- Capture request correlation and business dimensions such as application, project, team, user/session/conversation, use case, feature, workflow mode, tool used, and structured result type.
- Propagate correlation metadata to the OpenAI-compatible gateway path through headers so Kong, ai-gateway-service, and observability records can be joined.
- Emit business attribution metrics through the existing observability SDK path for Prometheus/Grafana consumption.
- Classify the three MVP AI entry points:
  - FX data query result generation
  - FX advisory report generation
  - Conversational dashboard generation
- Avoid double-counting by keeping token/cost calculation in the existing LLM metric path while adding low-cardinality business attribution labels as a companion metric.

## Capabilities

### New Capabilities
- `ai-cost-attribution`: Business-level AI usage attribution for AI Market Studio cost analysis across application, project, team, use case, feature, model, status, and request correlation.

### Modified Capabilities

None.

## Impact

- Backend API models and `/api/chat` request handling in `backend/models.py`, `backend/router.py`, and `backend/agent/agent.py`.
- Frontend chat payload construction in `ai-market-studio-ui/index.html`.
- Observability SDK usage in AI Market Studio, using the existing AI SRE observability ingestion path.
- Prometheus/Grafana dashboards or queries can add panels based on the new business attribution metric after the backend emits it.
- No changes to the public `/api/chat` response schema, existing AI Gateway routing, or connector data APIs are required for the MVP.
