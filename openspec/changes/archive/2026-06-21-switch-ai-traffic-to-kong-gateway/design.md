## Context

AI Market Studio currently creates an OpenAI-compatible `AsyncOpenAI` client from `OPENAI_BASE_URL`, with Kubernetes config already capable of pointing at an ai-gateway-service URL. The next product state is a Kong-fronted ai-gateway-service path where AI chat completion traffic enters an independently deployed Kong Gateway service first, then reaches ai-gateway-service and downstream model providers.

The latest ai-gateway-service repository includes local Kong OSS POC configuration, but its current GKE manifests still deploy only the FastAPI ai-gateway-service workload. This change treats Kong-on-GKE as part of the AI Market Studio integration scope so production traffic can actually follow the intended path.

The codebase still exposes `agent_mode` values of `legacy` and `workflow`, with `legacy` as the request default. Product direction is now to remove legacy orchestration and make workflow orchestration the only supported chat agent path. This migration must preserve the `/api/chat` response shape while changing the internal routing and orchestration contract.

## Goals / Non-Goals

**Goals:**
- Route AI chat completion traffic through Kong Gateway to ai-gateway-service using an environment-specific OpenAI-compatible base URL.
- Deploy Kong Gateway as an independent GKE workload and service in front of the existing ai-gateway-service Kubernetes service.
- Make workflow orchestration the only supported chat agent mode.
- Remove legacy agent mode from request schema, default behavior, tool selection, tests, and specs.
- Preserve workflow-mode market briefing, financial playbook, FX carry, source grounding, synthetic specialist data, and research-only outputs.
- Define which tool/MCP traffic is gateway-routed versus locally executed.
- Provide rollback by configuration for the AI base URL without restoring legacy orchestration.
- Add tests that prove gateway routing, workflow compatibility, failure behavior, and legacy rejection/removal.

**Non-Goals:**
- Rebuild the workflow runtime or financial playbook architecture.
- Route all external market data, news, FRED, or RAG traffic through Kong unless explicitly classified as gateway-routed tool/MCP traffic.
- Add new UI features.
- Add new financial analysis playbooks.
- Preserve legacy orchestration as a long-term product fallback.

## Decisions

### Decision 1: Kong is the AI base URL boundary

AI Market Studio will continue using an OpenAI-compatible client, but `OPENAI_BASE_URL` will point at the Kong service route for ai-gateway-service in deployed environments.

Alternative considered: add a separate gateway client abstraction immediately. That adds indirection before there is a second AI protocol to support. The current OpenAI-compatible boundary is enough for this migration and keeps the blast radius smaller.

### Decision 2: Kong is deployed independently in GKE

Kong Gateway will run as a separate Deployment and ClusterIP Service, for example `ai-gateway-kong.ai-gateway.svc.cluster.local`, and will route `/v1`, `/health`, and `/readiness` to the existing ai-gateway-service Kubernetes Service.

Alternative considered: run Kong as a sidecar in each ai-gateway-service Pod. Sidecar mode would couple app and gateway rollout, scaling, resources, and failure domains. A separate gateway workload better matches the platform-entry role and can later serve additional AI consumers.

### Decision 3: Kong uses Kubernetes service DNS as upstream

The GKE Kong declarative config will route to the existing ai-gateway-service Kubernetes Service, for example `http://ai-gateway.ai-gateway.svc.cluster.local`, with `strip_path: false` for `/v1` so OpenAI-compatible paths are preserved.

Alternative considered: reuse the local compose upstream `http://ai-gateway-service:4000`. That hostname is valid only inside the Docker Compose network and is not the production GKE service name.

### Decision 4: Workflow is the only supported chat orchestration mode

`agent_mode=legacy` will be removed from the public chat request contract. Omitted `agent_mode` requests will use workflow orchestration, or the field may be removed entirely if implementation chooses an internal-only workflow path.

Alternative considered: keep legacy as compatibility fallback during gateway migration. That would preserve a deprecated path and force duplicate gateway validation across two orchestration models.

### Decision 5: Rollback changes AI routing, not orchestration mode

Rollback means changing the AI base URL away from Kong to a previous OpenAI-compatible endpoint if needed. Rollback does not re-enable legacy orchestration.

Alternative considered: use legacy orchestration as rollback. That conflates routing rollback with product behavior rollback and would keep deprecated behavior alive.

### Decision 6: Tool/MCP boundaries must be explicit

Gateway-routed MCP/tool calls must emit enough metadata to identify gateway usage. Locally executed connectors such as market rates, news, FRED, and existing RAG calls must remain explicit so operators can distinguish local connector failures from gateway failures.

Alternative considered: claim all tool traffic is gateway-routed. The current code still executes several connectors locally, so that would create a misleading product contract.

### Decision 7: Preserve response shape while changing internals

`/api/chat` will continue returning `reply`, `data`, and `tool_used`. Workflow-specific details remain inside `data` and observability records.

Alternative considered: version the chat API for this migration. That is unnecessary if response shape remains stable and only `agent_mode=legacy` is removed.

## Risks / Trade-offs

- Gateway route mismatch or auth/header mismatch -> Add config-level tests and an integration test that asserts the OpenAI client receives the Kong base URL and expected headers/config.
- Kong deploys but bypasses ai-gateway-service -> Add GKE manifests and validation for `/health`, `/readiness`, `/v1/models`, and `/v1/chat/completions` through the Kong service DNS.
- Local compose hostname leaks into GKE config -> Use Kubernetes service DNS in GKE Kong config and test that manifests do not reference the compose-only hostname.
- Removing legacy breaks clients still sending `agent_mode=legacy` -> Treat as a breaking change, reject clearly, and document migration to workflow/default behavior.
- Workflow mode may not cover all legacy tool behaviors -> Add regression tests for core chat, market briefing, FX carry, source grounding, and existing connector-backed tool behavior.
- Gateway failures could look like model failures -> Map timeout/upstream/auth failures to clear API errors and add structured logs with route/mode/status metadata.
- Tool traffic boundaries may be misunderstood -> Document gateway-routed versus local connector paths and include observability labels for both.
- Rollback could be confused with feature rollback -> Document that routing rollback is config-only and does not restore legacy orchestration.

## Migration Plan

1. Add independent Kong GKE manifests using DB-less declarative config adapted for Kubernetes service DNS.
2. Validate Kong routes `/v1`, `/health`, and `/readiness` to the existing ai-gateway-service Kubernetes Service.
3. Update AI Market Studio environment configuration so `OPENAI_BASE_URL` points at the Kong service DNS.
4. Update chat request schema and agent runtime so workflow orchestration is the only supported mode.
5. Remove legacy tool set exposure and legacy prompt/runtime branches.
6. Preserve workflow tool definitions and workflow result shape.
7. Add gateway integration tests, workflow regression tests, and legacy removal tests.
8. Deploy with Kong base URL in dev, validate chat/workflow/FX carry paths, then promote.

Rollback strategy: set `OPENAI_BASE_URL` to the previous OpenAI-compatible upstream and redeploy/restart. Do not re-enable `legacy` agent mode.

## Open Questions

- What exact Kong service name should be canonical: `ai-gateway-kong`, `kong-ai-gateway`, or another platform naming convention?
- Which MCP connector calls are already available through ai-gateway-service versus still local to AI Market Studio?
- Should `agent_mode` be removed from `ChatRequest` entirely or retained as an optional field that only accepts `workflow` during a transition window?
