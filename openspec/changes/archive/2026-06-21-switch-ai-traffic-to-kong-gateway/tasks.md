## 1. Gateway Routing Contract

- [x] 1.1 Document the canonical Kong OpenAI-compatible route, required auth material, required headers, timeout expectations, and error categories.
- [x] 1.2 Add or update configuration tests proving `OPENAI_BASE_URL` can point to Kong, direct ai-gateway-service, or a local test double without code changes.
- [x] 1.3 Define the canonical GKE Kong service DNS and `/v1` base URL used by AI Market Studio.
- [x] 1.4 Update k8s/local environment configuration so deployed AI chat completion traffic points to the Kong Gateway route.
- [x] 1.5 Add gateway integration coverage proving the agent client is created with the configured Kong base URL.

## 2. Independent Kong GKE Deployment

- [x] 2.1 Add Kong DB-less declarative configuration for GKE that routes `/v1`, `/health`, and `/readiness` to the existing ai-gateway-service Kubernetes Service.
- [x] 2.2 Add an independent Kong Deployment in the AI gateway namespace.
- [x] 2.3 Add an internal Kong Kubernetes Service for in-cluster consumers such as AI Market Studio.
- [x] 2.4 Add manifest/config tests proving GKE Kong upstreams use Kubernetes service DNS and not Docker Compose-only hostnames.
- [x] 2.5 Add validation steps for `/health`, `/readiness`, `/v1/models`, and `/v1/chat/completions` through the Kong service DNS.

## 3. Remove Legacy Agent Mode

- [x] 3.1 Update `ChatRequest` schema so legacy mode is no longer accepted and omitted `agent_mode` requests use workflow behavior.
- [x] 3.2 Remove legacy prompt selection and legacy runtime branches from the agent execution path.
- [x] 3.3 Remove legacy tool set exposure and keep only approved workflow tool definitions for chat orchestration.
- [x] 3.4 Update schema, chat API, agent, and tool tests that currently assert legacy defaults or explicit legacy behavior.
- [x] 3.5 Add regression coverage proving `agent_mode=legacy` is rejected or impossible through the public request contract.

## 4. Preserve Workflow Compatibility

- [x] 4.1 Verify workflow mode remains gated predictably when workflow configuration is disabled, without falling back to legacy orchestration.
- [x] 4.2 Add regression coverage for collect market context, analyze market context, and generate market briefing under the single workflow orchestration path.
- [x] 4.3 Add coverage proving `/api/chat` still returns `reply`, `data`, and `tool_used` after legacy removal and gateway routing.
- [x] 4.4 Verify workflow step limits, timeouts, and partial source failure behavior remain intact.

## 5. Tool and MCP Traffic Boundaries

- [x] 5.1 Inventory current tool and connector paths as gateway-routed MCP/tool calls or local connector calls.
- [x] 5.2 Add observability/log metadata that identifies gateway-routed tool calls separately from local connector calls.
- [x] 5.3 Add tests for gateway-routed MCP/tool success and failure behavior where a gateway-backed connector is available.
- [x] 5.4 Document local connector paths for market rates, news, FRED, and existing RAG behavior if they remain local after this migration.

## 6. FX Analysis and Playbook Regression

- [x] 6.1 Add or update regression coverage for gateway-routed market briefing workflow behavior.
- [x] 6.2 Add or update regression coverage for FX carry playbook output under gateway-routed workflow execution.
- [x] 6.3 Verify source grounding, data gaps, synthetic specialist data labels, carry metrics, and research-only framing remain stable.
- [x] 6.4 Verify no legacy orchestration path is used for FX analysis or playbook requests.

## 7. Failure Handling, Rollback, and Documentation

- [x] 7.1 Map gateway timeout, auth, route, and upstream failures to clear chat API error behavior.
- [x] 7.2 Add logs or metrics that distinguish gateway failures from local connector failures.
- [x] 7.3 Document rollback by changing `OPENAI_BASE_URL` to a previous OpenAI-compatible upstream without restoring legacy orchestration.
- [x] 7.4 Update user/operator documentation for the workflow-only chat path and Kong-fronted ai-gateway-service deployment.
- [x] 7.5 Run the full relevant regression suite for schema, chat API, agent workflow, gateway integration, Kong deployment manifests, tool boundaries, and FX playbooks.
