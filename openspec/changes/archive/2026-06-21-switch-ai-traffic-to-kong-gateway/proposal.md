## Why

AI Market Studio needs to move its AI traffic onto the new Kong-fronted ai-gateway-service so gateway routing, auth, observability, and AI gateway features are exercised through the product path. The migration is also the right moment to remove the remaining legacy agent orchestration path so workflow-mode financial analysis becomes the single supported chat orchestration model.

## What Changes

- Route AI chat completion traffic from AI Market Studio through Kong Gateway to ai-gateway-service using an environment-specific OpenAI-compatible base URL.
- Deploy Kong Gateway as an independent GKE workload in the AI gateway namespace, with AI Market Studio using the Kong service DNS as its AI base URL.
- Define gateway request contract expectations for routing, auth/header propagation, timeout behavior, error mapping, observability, and rollback.
- Preserve the existing `/api/chat` response shape with `reply`, `data`, and `tool_used`.
- Preserve workflow-mode intent tools, market briefing workflows, financial playbooks, FX carry output, source grounding, and research-only guardrails through the gateway migration.
- Define MCP/tool traffic boundaries so gateway-routed calls and locally executed connector calls are explicit and observable.
- **BREAKING**: Remove `legacy` agent mode as a supported chat orchestration mode and make workflow orchestration the only product-supported agent mode.
- **BREAKING**: Remove the legacy default behavior where omitted `agent_mode` requests run legacy tool orchestration.

## Capabilities

### New Capabilities
- `ai-gateway-routing`: Defines how AI Market Studio routes AI traffic through Kong Gateway to ai-gateway-service, including configuration, headers, error behavior, observability, and rollback.
- `kong-gke-deployment`: Defines the independent Kong Gateway deployment model for GKE, including service DNS, DB-less config, routing to ai-gateway-service, and health/readiness validation.
- `gateway-tool-traffic-boundaries`: Defines which tool/MCP traffic is gateway-routed versus locally executed and how those paths are made observable.

### Modified Capabilities
- `agent-orchestration-mode`: Remove legacy orchestration as the default and supported product mode; workflow orchestration becomes the only supported chat agent mode.
- `intent-level-agent-workflows`: Require intent-level workflow behavior to remain compatible when chat completions are routed through Kong Gateway.
- `agent-workflow-guardrails`: Extend workflow failure and observability requirements to include gateway-routed AI requests.
- `financial-analysis-playbooks`: Require financial playbook outputs, including FX carry demo outputs, to remain stable under gateway-routed workflow execution.

## Impact

- Backend configuration: `OPENAI_BASE_URL`, gateway-related settings, local/dev/k8s config, and rollback configuration.
- Backend chat API: `ChatRequest.agent_mode`, request validation, default orchestration behavior, and related tests.
- Agent runtime: `backend/agent/agent.py`, tool definitions, workflow execution, error handling, and observability metadata.
- Tool and connector layer: MCP/tool connector integration, RAG connector boundary, and locally executed market/news/FRED connector documentation.
- Kubernetes deployment: independent Kong workload/service, Kong DB-less config, Kong gateway base URL, secrets/configmaps, and environment-specific routing.
- Tests: schema tests, chat API tests, agent workflow tests, gateway integration tests, FX carry/playbook regression tests, and rollback/failure tests.
