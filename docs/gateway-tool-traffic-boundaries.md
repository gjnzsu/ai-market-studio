# Gateway Tool Traffic Boundaries

## Gateway-Routed

LLM chat completions are routed through `OPENAI_BASE_URL`. In Kubernetes this should point at Kong, for example `http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1`, so OpenAI-compatible traffic carries gateway policy and observability.

MCP-backed tools are gateway-routed only when they are explicitly configured through `ai-gateway-service` and Kong. Until a tool connector is moved behind that service boundary, it should not be counted as gateway-mediated tool traffic.

Use the observability label `ai_path=gateway` for LLM traffic that flows through Kong.

## Local Connector Paths

Current backend tool dispatch still uses local connector paths for these integrations:

- `backend.connectors.exchangerate_host`, or the mock connector when enabled.
- `backend.connectors.news_connector`.
- `backend.connectors.fred_connector`.
- `backend.connectors.rag_connector`.

These connectors remain local until they are moved behind `ai-gateway-service` and Kong.

Use the observability label `tool_path=local_connector` for these tool calls.
