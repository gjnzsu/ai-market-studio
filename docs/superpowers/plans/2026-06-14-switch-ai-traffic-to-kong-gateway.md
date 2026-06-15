# Switch AI Traffic To Kong Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route AI Market Studio AI traffic through an independently deployed Kong Gateway in GKE, remove legacy agent orchestration, and preserve workflow-mode FX analysis behavior.

**Architecture:** AI Market Studio keeps its OpenAI-compatible client and points `OPENAI_BASE_URL` at `http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1`. Kong runs as an independent DB-less GKE workload and routes `/v1`, `/health`, and `/readiness` to the existing `ai-gateway.ai-gateway.svc.cluster.local` service. Workflow orchestration becomes the only supported chat path; legacy mode is removed from public schema, runtime branching, and tests.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, Kubernetes YAML, Kong OSS DB-less declarative config, OpenSpec.

---

## File Structure

- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`
  - Track OpenSpec checkbox completion after each matching plan task is implemented and verified.
- Modify: `k8s/configmap.yaml`
  - Set AI Market Studio deployed `OPENAI_BASE_URL` to the Kong service DNS.
- Create: `k8s/kong-config.yaml`
  - Store Kong DB-less declarative config for GKE.
- Create: `k8s/kong-deployment.yaml`
  - Deploy Kong as an independent workload in the AI gateway namespace.
- Create: `k8s/kong-service.yaml`
  - Expose Kong proxy internally for in-cluster consumers.
- Create: `backend/tests/unit/test_kong_manifests.py`
  - Validate Kong manifests and service DNS routing contract.
- Modify: `backend/tests/e2e/test_gateway_integration.py`
  - Verify configured gateway base URL and request headers.
- Modify: `backend/models.py`
  - Remove legacy mode from `ChatRequest` schema or retain only optional workflow-compatible field.
- Modify: `backend/router.py`
  - Default chat requests to workflow orchestration and reject/avoid legacy.
- Modify: `backend/agent/agent.py`
  - Remove legacy prompt/runtime branch and add gateway-aware request metadata.
- Modify: `backend/agent/tools.py`
  - Remove legacy tool definition exports for chat orchestration; keep dispatch support only for tools still used by workflows or API internals.
- Modify: `backend/tests/unit/test_schemas.py`
  - Update schema expectations for workflow-only behavior.
- Modify: `backend/tests/e2e/test_chat_api.py`
  - Update chat API tests for workflow default, legacy rejection, response shape, timeout behavior.
- Modify: `backend/tests/unit/test_tools.py`
  - Update tool definition tests for workflow-only chat tool exposure.
- Modify: `backend/tests/agent/test_agent.py`
  - Update runtime tests for workflow-only prompt/tool behavior and no legacy fallback.
- Modify: `backend/tests/unit/test_workflows.py`
  - Preserve market briefing, FX carry, source grounding, partial source failure behavior.
- Create or modify: `docs/deployments/kong-gateway-integration.md`
  - Operator docs for GKE deployment, validation, traffic path, rollback.
- Create or modify: `docs/gateway-tool-traffic-boundaries.md`
  - Inventory gateway-routed versus local connector paths.

---

## Task 1.1: Document Gateway Route Contract

Maps to OpenSpec: 1.1

**Files:**
- Create: `docs/deployments/kong-gateway-integration.md`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Write the contract document**

Include this content:

```markdown
# Kong Gateway Integration

## Canonical Traffic Path

AI Market Studio sends OpenAI-compatible AI traffic to:

```text
http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1
```

Kong routes to:

```text
http://ai-gateway.ai-gateway.svc.cluster.local
```

Effective path:

```text
ai-market-studio -> ai-gateway-kong -> ai-gateway -> model provider
```

## Routes

- `/v1/chat/completions`: OpenAI-compatible chat completions
- `/v1/models`: OpenAI-compatible model listing
- `/health`: ai-gateway-service liveness through Kong
- `/readiness`: ai-gateway-service readiness through Kong

## Headers

- `Content-Type: application/json`
- `X-Request-ID`: generated or propagated for request correlation
- `X-Consumer-Service: ai-market-studio`: identifies AI Market Studio to ai-gateway-service policy and observability

## Timeout And Error Categories

- Kong route/auth/upstream failures are gateway failures.
- Provider failures returned by ai-gateway-service are AI upstream failures.
- Local market, news, FRED, or RAG connector failures are local connector failures.

## Rollback

Rollback changes `OPENAI_BASE_URL` to a previous OpenAI-compatible upstream. Rollback does not restore legacy agent orchestration.
```

- [ ] **Step 2: Verify document exists**

Run: `Test-Path docs\deployments\kong-gateway-integration.md`

Expected: `True`

- [ ] **Step 3: Mark OpenSpec task 1.1 complete**

Change `- [ ] 1.1` to `- [x] 1.1` in `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`.

## Task 1.2: Add Base URL Configuration Tests

Maps to OpenSpec: 1.2

**Files:**
- Modify: `backend/tests/e2e/test_gateway_integration.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add failing tests**

Append tests that assert these base URLs are accepted by the agent client:

```python
def test_agent_client_accepts_kong_gateway_base_url(monkeypatch):
    captured = {}

    def fake_openai(**kwargs):
        captured.update(kwargs)
        mock = AsyncMock()
        mock.chat.completions.create = AsyncMock(return_value=make_response(content="ok"))
        return mock

    monkeypatch.setattr("backend.agent.agent.settings.openai_base_url", "http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1")
    monkeypatch.setattr("backend.agent.agent.AsyncOpenAI", fake_openai)

    # call run_agent with injected fake response in an async test
    # assert captured["base_url"] == "http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1"
```

Prefer a real async pytest test using `await run_agent(...)` and a mocked `AsyncOpenAI`.

- [ ] **Step 2: Verify RED**

Run: `pytest -q backend/tests/e2e/test_gateway_integration.py`

Expected: FAIL if headers/base URL are not captured or asserted yet.

- [ ] **Step 3: Implement minimal code if needed**

If `backend/agent/agent.py` already passes `base_url=settings.openai_base_url`, no production change is required for base URL. If request metadata is needed, add only the missing client kwargs.

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q backend/tests/e2e/test_gateway_integration.py`

Expected: PASS.

- [ ] **Step 5: Mark OpenSpec task 1.2 complete**

Change `- [ ] 1.2` to `- [x] 1.2`.

## Task 1.3: Define Canonical Kong Service DNS

Maps to OpenSpec: 1.3

**Files:**
- Modify: `docs/deployments/kong-gateway-integration.md`
- Modify: `k8s/configmap.yaml`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Document canonical DNS**

Use:

```text
http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1
```

- [ ] **Step 2: Verify reference**

Run: `rg "ai-gateway-kong.ai-gateway.svc.cluster.local/v1" docs k8s`

Expected: At least documentation hit; config hit after Task 1.4.

- [ ] **Step 3: Mark OpenSpec task 1.3 complete**

Change `- [ ] 1.3` to `- [x] 1.3`.

## Task 1.4: Update AI Market Studio Gateway Config

Maps to OpenSpec: 1.4

**Files:**
- Modify: `k8s/configmap.yaml`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Write failing manifest expectation**

Add or prepare `backend/tests/unit/test_kong_manifests.py` with an assertion that `k8s/configmap.yaml` contains:

```yaml
OPENAI_BASE_URL: "http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1"
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q backend/tests/unit/test_kong_manifests.py`

Expected: FAIL because current config points at `http://ai-gateway.ai-gateway.svc.cluster.local/v1`.

- [ ] **Step 3: Update config**

Change `OPENAI_BASE_URL` in `k8s/configmap.yaml` to:

```yaml
OPENAI_BASE_URL: "http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1"
```

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q backend/tests/unit/test_kong_manifests.py`

Expected: PASS.

- [ ] **Step 5: Mark OpenSpec task 1.4 complete**

Change `- [ ] 1.4` to `- [x] 1.4`.

## Task 1.5: Gateway Client Integration Coverage

Maps to OpenSpec: 1.5

**Files:**
- Modify: `backend/tests/e2e/test_gateway_integration.py`
- Modify: `backend/agent/agent.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add failing request metadata test**

Test that the agent client sends AI Market Studio identity metadata through the OpenAI-compatible client HTTP headers. Target behavior:

```python
assert "X-Consumer-Service" in captured_headers
assert captured_headers["X-Consumer-Service"] == "ai-market-studio"
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q backend/tests/e2e/test_gateway_integration.py`

Expected: FAIL because current `AsyncOpenAI` construction does not set default headers.

- [ ] **Step 3: Implement minimal header support**

In `backend/agent/agent.py`, pass default headers when constructing `AsyncOpenAI`:

```python
client = AsyncOpenAI(
    api_key=settings.openai_api_key.get_secret_value(),
    base_url=settings.openai_base_url,
    default_headers={"X-Consumer-Service": "ai-market-studio"},
    http_client=httpx.AsyncClient(trust_env=False),
)
```

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q backend/tests/e2e/test_gateway_integration.py`

Expected: PASS.

- [ ] **Step 5: Mark OpenSpec task 1.5 complete**

Change `- [ ] 1.5` to `- [x] 1.5`.

## Task 2.1: Add Kong DB-less GKE Config

Maps to OpenSpec: 2.1

**Files:**
- Create: `k8s/kong-config.yaml`
- Modify: `backend/tests/unit/test_kong_manifests.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add failing manifest test**

Assert that `k8s/kong-config.yaml` defines a ConfigMap named `ai-gateway-kong-config`, contains `/v1`, `/health`, `/readiness`, uses `strip_path: false`, and routes to:

```text
http://ai-gateway.ai-gateway.svc.cluster.local
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q backend/tests/unit/test_kong_manifests.py`

Expected: FAIL because the file does not exist.

- [ ] **Step 3: Create manifest**

Create `k8s/kong-config.yaml` containing:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ai-gateway-kong-config
  namespace: ai-gateway
data:
  kong.yml: |
    _format_version: "3.0"
    _transform: true
    services:
      - name: ai-gateway-service
        url: http://ai-gateway.ai-gateway.svc.cluster.local
        connect_timeout: 5000
        read_timeout: 60000
        write_timeout: 60000
        retries: 2
        routes:
          - name: ai-gateway-v1
            paths:
              - /v1
            strip_path: false
          - name: ai-gateway-health
            paths:
              - /health
            strip_path: false
          - name: ai-gateway-readiness
            paths:
              - /readiness
            strip_path: false
    plugins:
      - name: correlation-id
        config:
          header_name: X-Request-ID
          generator: uuid
          echo_downstream: true
      - name: rate-limiting
        config:
          minute: 120
          policy: local
```

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q backend/tests/unit/test_kong_manifests.py`

Expected: PASS for config assertions.

- [ ] **Step 5: Mark OpenSpec task 2.1 complete**

Change `- [ ] 2.1` to `- [x] 2.1`.

## Task 2.2: Add Independent Kong Deployment

Maps to OpenSpec: 2.2

**Files:**
- Create: `k8s/kong-deployment.yaml`
- Modify: `backend/tests/unit/test_kong_manifests.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add failing deployment manifest test**

Assert:

```python
assert manifest["kind"] == "Deployment"
assert manifest["metadata"]["name"] == "ai-gateway-kong"
assert container["image"].startswith("kong:")
assert container["env"] includes KONG_DATABASE=off
assert container["ports"] includes containerPort 8000
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q backend/tests/unit/test_kong_manifests.py`

Expected: FAIL because deployment file does not exist.

- [ ] **Step 3: Create deployment**

Create a Kong deployment using `kong:3`, DB-less config mounted from `ai-gateway-kong-config`, proxy port `8000`, admin port disabled or internal-only, and resource requests/limits similar in scale to the gateway service.

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q backend/tests/unit/test_kong_manifests.py`

Expected: PASS.

- [ ] **Step 5: Mark OpenSpec task 2.2 complete**

Change `- [ ] 2.2` to `- [x] 2.2`.

## Task 2.3: Add Internal Kong Service

Maps to OpenSpec: 2.3

**Files:**
- Create: `k8s/kong-service.yaml`
- Modify: `backend/tests/unit/test_kong_manifests.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add failing service manifest test**

Assert:

```python
assert manifest["kind"] == "Service"
assert manifest["metadata"]["name"] == "ai-gateway-kong"
assert manifest["spec"]["type"] == "ClusterIP"
assert manifest["spec"]["ports"][0]["port"] == 80
assert manifest["spec"]["ports"][0]["targetPort"] == 8000
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q backend/tests/unit/test_kong_manifests.py`

Expected: FAIL because service file does not exist.

- [ ] **Step 3: Create service**

Create `k8s/kong-service.yaml` as an internal ClusterIP service selecting `app: ai-gateway-kong`.

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q backend/tests/unit/test_kong_manifests.py`

Expected: PASS.

- [ ] **Step 5: Mark OpenSpec task 2.3 complete**

Change `- [ ] 2.3` to `- [x] 2.3`.

## Task 2.4: Validate Kong Manifests Use GKE DNS

Maps to OpenSpec: 2.4

**Files:**
- Modify: `backend/tests/unit/test_kong_manifests.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add failing guard test**

Assert none of the GKE Kong manifests contain:

```text
ai-gateway-service:4000
```

and `k8s/kong-config.yaml` contains:

```text
ai-gateway.ai-gateway.svc.cluster.local
```

- [ ] **Step 2: Verify RED/GREEN**

Run before and after config creation as appropriate:

`pytest -q backend/tests/unit/test_kong_manifests.py`

- [ ] **Step 3: Mark OpenSpec task 2.4 complete**

Change `- [ ] 2.4` to `- [x] 2.4`.

## Task 2.5: Add Kong Validation Steps

Maps to OpenSpec: 2.5

**Files:**
- Modify: `docs/deployments/kong-gateway-integration.md`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add validation commands**

Add:

```powershell
kubectl apply -f k8s/kong-config.yaml
kubectl apply -f k8s/kong-deployment.yaml
kubectl apply -f k8s/kong-service.yaml
kubectl -n ai-gateway rollout status deployment/ai-gateway-kong
kubectl -n ai-gateway run kong-smoke --rm -i --restart=Never --image=curlimages/curl -- `
  http://ai-gateway-kong.ai-gateway.svc.cluster.local/health
kubectl -n ai-gateway run kong-models --rm -i --restart=Never --image=curlimages/curl -- `
  http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1/models
```

- [ ] **Step 2: Verify docs include all endpoints**

Run: `rg "/health|/readiness|/v1/models|/v1/chat/completions" docs\deployments\kong-gateway-integration.md`

Expected: all four endpoint names appear.

- [ ] **Step 3: Mark OpenSpec task 2.5 complete**

Change `- [ ] 2.5` to `- [x] 2.5`.

## Task 3.1: Remove Legacy From ChatRequest Schema

Maps to OpenSpec: 3.1

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/tests/unit/test_schemas.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Update tests first**

Change schema tests so:

```python
def test_chat_request_defaults_to_workflow_agent_mode():
    req = ChatRequest(message="What is EUR/USD?")
    assert req.agent_mode == "workflow"

def test_chat_request_rejects_explicit_legacy_agent_mode():
    with pytest.raises(ValidationError):
        ChatRequest(message="What is EUR/USD?", agent_mode="legacy")
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q backend/tests/unit/test_schemas.py`

Expected: FAIL because current default is `legacy` and explicit legacy is accepted.

- [ ] **Step 3: Implement schema change**

In `backend/models.py`, change:

```python
AgentMode = Literal["workflow"]
agent_mode: AgentMode = "workflow"
```

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q backend/tests/unit/test_schemas.py`

Expected: PASS.

- [ ] **Step 5: Mark OpenSpec task 3.1 complete**

Change `- [ ] 3.1` to `- [x] 3.1`.

## Task 3.2: Remove Legacy Runtime Branches

Maps to OpenSpec: 3.2

**Files:**
- Modify: `backend/agent/agent.py`
- Modify: `backend/tests/agent/test_agent.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Update tests first**

Replace legacy branch tests with workflow-only expectations:

```python
assert "collect_market_context" in names
assert "generate_market_briefing" in names
```

Remove tests that expect `agent_mode="legacy"` to use legacy tools.

- [ ] **Step 2: Verify RED**

Run: `pytest -q backend/tests/agent/test_agent.py`

Expected: FAIL while `run_agent` still defaults to legacy and has legacy prompt selection.

- [ ] **Step 3: Implement minimal runtime change**

In `backend/agent/agent.py`:

```python
AgentMode = Literal["workflow"]
agent_mode: AgentMode = "workflow"
```

Use `WORKFLOW_SYSTEM_PROMPT` unconditionally for chat orchestration.

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q backend/tests/agent/test_agent.py`

Expected: PASS after related test updates.

- [ ] **Step 5: Mark OpenSpec task 3.2 complete**

Change `- [ ] 3.2` to `- [x] 3.2`.

## Task 3.3: Remove Legacy Tool Set Exposure

Maps to OpenSpec: 3.3

**Files:**
- Modify: `backend/agent/tools.py`
- Modify: `backend/tests/unit/test_tools.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Update tests first**

Change tests so:

```python
def test_tool_definitions_expose_only_workflow_tools():
    assert _tool_names(TOOL_DEFINITIONS) == [
        "collect_market_context",
        "analyze_market_context",
        "generate_market_briefing",
    ]

def test_get_tool_definitions_returns_workflow_tools():
    assert get_tool_definitions("workflow") == WORKFLOW_TOOL_DEFINITIONS
    assert get_tool_definitions(None) == WORKFLOW_TOOL_DEFINITIONS
```

Add a legacy rejection expectation if keeping `get_tool_definitions(agent_mode)` validation.

- [ ] **Step 2: Verify RED**

Run: `pytest -q backend/tests/unit/test_tools.py`

Expected: FAIL because current `TOOL_DEFINITIONS` aliases legacy tools.

- [ ] **Step 3: Implement minimal change**

Set:

```python
TOOL_DEFINITIONS = WORKFLOW_TOOL_DEFINITIONS
```

Update `get_tool_definitions` to return workflow tools only or raise `AgentError` for unsupported mode.

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q backend/tests/unit/test_tools.py`

Expected: PASS.

- [ ] **Step 5: Mark OpenSpec task 3.3 complete**

Change `- [ ] 3.3` to `- [x] 3.3`.

## Task 3.4: Update Legacy-Dependent Tests

Maps to OpenSpec: 3.4

**Files:**
- Modify: `backend/tests/unit/test_schemas.py`
- Modify: `backend/tests/e2e/test_chat_api.py`
- Modify: `backend/tests/agent/test_agent.py`
- Modify: `backend/tests/unit/test_tools.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Run focused suite**

Run:

```powershell
pytest -q backend/tests/unit/test_schemas.py backend/tests/e2e/test_chat_api.py backend/tests/agent/test_agent.py backend/tests/unit/test_tools.py
```

Expected: identify remaining legacy assertions.

- [ ] **Step 2: Update each remaining legacy assertion**

Replace default legacy expectations with workflow expectations. Delete tests whose only value was preserving legacy behavior.

- [ ] **Step 3: Verify GREEN**

Run the same focused suite.

Expected: PASS.

- [ ] **Step 4: Mark OpenSpec task 3.4 complete**

Change `- [ ] 3.4` to `- [x] 3.4`.

## Task 3.5: Add Legacy Rejection Regression

Maps to OpenSpec: 3.5

**Files:**
- Modify: `backend/tests/e2e/test_chat_api.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add failing API test**

```python
def test_chat_rejects_legacy_agent_mode(app_client):
    resp = app_client.post(
        "/api/chat",
        json={"message": "What is EUR/USD?", "agent_mode": "legacy"},
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q backend/tests/e2e/test_chat_api.py::test_chat_rejects_legacy_agent_mode`

Expected: FAIL before schema change; PASS after Task 3.1.

- [ ] **Step 3: Verify GREEN**

Run: `pytest -q backend/tests/e2e/test_chat_api.py`

Expected: PASS.

- [ ] **Step 4: Mark OpenSpec task 3.5 complete**

Change `- [ ] 3.5` to `- [x] 3.5`.

## Task 4.1: Verify Workflow Disabled Behavior

Maps to OpenSpec: 4.1

**Files:**
- Modify: `backend/router.py`
- Modify: `backend/tests/e2e/test_chat_api.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Update test first**

Ensure omitted `agent_mode` is rejected when workflow mode is disabled:

```python
def test_chat_default_workflow_mode_disabled_is_rejected(app_client, monkeypatch):
    monkeypatch.setattr("backend.router.settings.enable_agent_workflow_mode", False)
    resp = app_client.post("/api/chat", json={"message": "Brief EUR/USD"})
    assert resp.status_code == 403
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q backend/tests/e2e/test_chat_api.py::test_chat_default_workflow_mode_disabled_is_rejected`

Expected: FAIL if omitted mode still runs legacy.

- [ ] **Step 3: Implement minimal router change**

In `backend/router.py`, treat every chat request as workflow and apply the workflow-enabled guard before calling `run_agent`.

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q backend/tests/e2e/test_chat_api.py`

Expected: PASS.

- [ ] **Step 5: Mark OpenSpec task 4.1 complete**

Change `- [ ] 4.1` to `- [x] 4.1`.

## Task 4.2: Workflow Tool Regression

Maps to OpenSpec: 4.2

**Files:**
- Modify: `backend/tests/unit/test_workflows.py`
- Modify: `backend/tests/agent/test_agent.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Run existing workflow tests**

Run: `pytest -q backend/tests/unit/test_workflows.py backend/tests/agent/test_agent.py`

Expected: PASS after workflow-only updates.

- [ ] **Step 2: Add missing coverage if absent**

Ensure tests cover `collect_market_context`, `analyze_market_context`, and `generate_market_briefing`.

- [ ] **Step 3: Mark OpenSpec task 4.2 complete**

Change `- [ ] 4.2` to `- [x] 4.2`.

## Task 4.3: Chat Response Shape Regression

Maps to OpenSpec: 4.3

**Files:**
- Modify: `backend/tests/e2e/test_chat_api.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add or update response shape test**

Ensure workflow default response has exactly:

```python
assert set(resp.json().keys()) == {"reply", "data", "tool_used"}
```

- [ ] **Step 2: Verify**

Run: `pytest -q backend/tests/e2e/test_chat_api.py`

Expected: PASS.

- [ ] **Step 3: Mark OpenSpec task 4.3 complete**

Change `- [ ] 4.3` to `- [x] 4.3`.

## Task 4.4: Workflow Limits And Partial Failure Regression

Maps to OpenSpec: 4.4

**Files:**
- Modify: `backend/tests/e2e/test_chat_api.py`
- Modify: `backend/tests/unit/test_workflows.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Verify focused tests**

Run:

```powershell
pytest -q backend/tests/e2e/test_chat_api.py::test_chat_workflow_timeout_returns_504 backend/tests/unit/test_workflows.py
```

- [ ] **Step 2: Add missing assertions for partial source warnings**

If missing, add tests that optional source failures return warnings in workflow data rather than crashing the whole workflow.

- [ ] **Step 3: Mark OpenSpec task 4.4 complete**

Change `- [ ] 4.4` to `- [x] 4.4`.

## Task 5.1: Inventory Tool Traffic Boundaries

Maps to OpenSpec: 5.1

**Files:**
- Create: `docs/gateway-tool-traffic-boundaries.md`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Create inventory**

Document:

```markdown
# Gateway Tool Traffic Boundaries

## Gateway-Routed

- LLM chat completions through `OPENAI_BASE_URL`
- MCP-backed tools only when configured through ai-gateway-service/Kong

## Local Connector Paths

- FX rates: `backend.connectors.exchangerate_host` or mock connector
- News: `backend.connectors.news_connector`
- FRED: `backend.connectors.fred_connector`
- RAG: `backend.connectors.rag_connector` until explicitly moved behind gateway

## Observability Labels

- `ai_path=gateway` for Kong/ai-gateway-service AI calls
- `tool_path=local_connector` for local connector calls
```

- [ ] **Step 2: Verify**

Run: `rg "Gateway-Routed|Local Connector Paths|tool_path" docs\gateway-tool-traffic-boundaries.md`

Expected: all terms found.

- [ ] **Step 3: Mark OpenSpec task 5.1 complete**

Change `- [ ] 5.1` to `- [x] 5.1`.

## Task 5.2: Add Tool Path Observability Metadata

Maps to OpenSpec: 5.2

**Files:**
- Modify: `backend/agent/agent.py`
- Modify: `backend/agent/tools.py`
- Modify: `backend/tests/agent/test_agent.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add failing log metadata test**

Use `caplog` to assert workflow tool calls log mode, tool name, and local/gateway path metadata.

- [ ] **Step 2: Verify RED**

Run: `pytest -q backend/tests/agent/test_agent.py`

Expected: FAIL until metadata exists.

- [ ] **Step 3: Implement minimal logging**

Add log fields to tool call logging:

```python
logger.info(
    "Tool call: mode=%s tool=%s tool_path=%s args=%s",
    agent_mode,
    tool_name,
    "local_connector",
    tool_args,
)
```

Use `gateway` only for actual gateway-backed tool paths once implemented.

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q backend/tests/agent/test_agent.py`

Expected: PASS.

- [ ] **Step 5: Mark OpenSpec task 5.2 complete**

Change `- [ ] 5.2` to `- [x] 5.2`.

## Task 5.3: Gateway Tool Success/Failure Tests

Maps to OpenSpec: 5.3

**Files:**
- Modify: `backend/tests/agent/test_agent.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add tests only for currently available gateway-backed tool paths**

If no MCP gateway-backed connector exists in this repo yet, add a skipped or documented test marker with reason:

```python
pytest.skip("No gateway-backed MCP tool connector is implemented in ai-market-studio yet")
```

Do not fake a gateway-backed tool path.

- [ ] **Step 2: Verify**

Run: `pytest -q backend/tests/agent/test_agent.py`

Expected: PASS or SKIP with explicit reason.

- [ ] **Step 3: Mark OpenSpec task 5.3 complete only if behavior is represented**

Change `- [ ] 5.3` to `- [x] 5.3` when either real tests exist or explicit documented skip is accepted.

## Task 5.4: Document Local Connector Paths

Maps to OpenSpec: 5.4

**Files:**
- Modify: `docs/gateway-tool-traffic-boundaries.md`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Document connector paths**

Include module names and current routing status for market rates, news, FRED, and RAG.

- [ ] **Step 2: Verify**

Run: `rg "exchangerate|news_connector|fred_connector|rag_connector" docs\gateway-tool-traffic-boundaries.md`

Expected: all connector names found.

- [ ] **Step 3: Mark OpenSpec task 5.4 complete**

Change `- [ ] 5.4` to `- [x] 5.4`.

## Task 6.1: Market Briefing Gateway Regression

Maps to OpenSpec: 6.1

**Files:**
- Modify: `backend/tests/agent/test_agent.py`
- Modify: `backend/tests/unit/test_workflows.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add or update regression**

Ensure market briefing uses workflow tools with gateway base URL configured.

- [ ] **Step 2: Verify**

Run: `pytest -q backend/tests/agent/test_agent.py backend/tests/unit/test_workflows.py`

Expected: PASS.

- [ ] **Step 3: Mark OpenSpec task 6.1 complete**

Change `- [ ] 6.1` to `- [x] 6.1`.

## Task 6.2: FX Carry Gateway Regression

Maps to OpenSpec: 6.2

**Files:**
- Modify: `backend/tests/agent/test_agent.py`
- Modify: `backend/tests/unit/test_workflows.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Preserve existing FX carry tests**

Keep or update tests asserting:

```python
assert tool_summary["playbook"]["id"] == "fx_carry"
assert tool_summary["specialist_data"]["source"] == "synthetic"
assert tool_summary["carry_metrics"]["source"] == "synthetic"
```

- [ ] **Step 2: Verify**

Run: `pytest -q backend/tests/agent/test_agent.py backend/tests/unit/test_workflows.py`

Expected: PASS.

- [ ] **Step 3: Mark OpenSpec task 6.2 complete**

Change `- [ ] 6.2` to `- [x] 6.2`.

## Task 6.3: Source Grounding And Research-Only Regression

Maps to OpenSpec: 6.3

**Files:**
- Modify: `backend/tests/unit/test_workflows.py`
- Modify: `backend/tests/unit/test_financial_playbooks.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Run financial workflow tests**

Run:

```powershell
pytest -q backend/tests/unit/test_workflows.py backend/tests/unit/test_financial_playbooks.py backend/tests/unit/test_synthetic_specialist_data.py
```

- [ ] **Step 2: Add missing assertions if gaps appear**

Assert source grounding, data gaps, synthetic labels, carry metrics, and research-only framing remain present.

- [ ] **Step 3: Mark OpenSpec task 6.3 complete**

Change `- [ ] 6.3` to `- [x] 6.3`.

## Task 6.4: No Legacy In FX Analysis

Maps to OpenSpec: 6.4

**Files:**
- Modify: `backend/tests/agent/test_agent.py`
- Modify: `backend/tests/unit/test_tools.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add guard assertions**

Assert FX analysis/playbook requests expose workflow tools only and do not include legacy low-level tool sets.

- [ ] **Step 2: Verify**

Run: `pytest -q backend/tests/agent/test_agent.py backend/tests/unit/test_tools.py`

Expected: PASS.

- [ ] **Step 3: Mark OpenSpec task 6.4 complete**

Change `- [ ] 6.4` to `- [x] 6.4`.

## Task 7.1: Map Gateway Failure Behavior

Maps to OpenSpec: 7.1

**Files:**
- Modify: `backend/router.py`
- Modify: `backend/tests/e2e/test_chat_api.py`
- Modify: `docs/deployments/kong-gateway-integration.md`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add failing gateway failure test**

Mock `run_agent` or OpenAI client to raise a gateway-like timeout/upstream exception. Assert clear API error behavior.

- [ ] **Step 2: Verify RED**

Run: `pytest -q backend/tests/e2e/test_chat_api.py`

Expected: FAIL if gateway errors collapse into generic 500.

- [ ] **Step 3: Implement minimal mapping**

Map timeout to 504 and gateway upstream/auth failures to clear 502/503-style errors without masking local `ConnectorError`.

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q backend/tests/e2e/test_chat_api.py`

Expected: PASS.

- [ ] **Step 5: Mark OpenSpec task 7.1 complete**

Change `- [ ] 7.1` to `- [x] 7.1`.

## Task 7.2: Distinguish Gateway And Local Connector Failures

Maps to OpenSpec: 7.2

**Files:**
- Modify: `backend/router.py`
- Modify: `backend/agent/agent.py`
- Modify: `backend/tests/e2e/test_chat_api.py`
- Modify: `backend/tests/agent/test_agent.py`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add caplog tests**

Assert gateway failures include `ai_path=gateway` and connector failures remain connector-specific.

- [ ] **Step 2: Verify RED**

Run focused tests for chat and agent logs.

- [ ] **Step 3: Implement minimal structured log text**

Use stable key-value log fragments such as `ai_path=gateway` and `tool_path=local_connector`.

- [ ] **Step 4: Verify GREEN**

Run focused tests.

- [ ] **Step 5: Mark OpenSpec task 7.2 complete**

Change `- [ ] 7.2` to `- [x] 7.2`.

## Task 7.3: Document Rollback

Maps to OpenSpec: 7.3

**Files:**
- Modify: `docs/deployments/kong-gateway-integration.md`
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Add rollback section**

Include:

```powershell
kubectl patch configmap ai-market-studio-config `
  --type merge `
  -p '{"data":{"OPENAI_BASE_URL":"http://ai-gateway.ai-gateway.svc.cluster.local/v1"}}'
kubectl rollout restart deployment/ai-market-studio
```

State explicitly that rollback does not restore legacy orchestration.

- [ ] **Step 2: Verify**

Run: `rg "rollback|legacy orchestration" docs\deployments\kong-gateway-integration.md`

Expected: both terms found.

- [ ] **Step 3: Mark OpenSpec task 7.3 complete**

Change `- [ ] 7.3` to `- [x] 7.3`.

## Task 7.4: Update Operator Documentation

Maps to OpenSpec: 7.4

**Files:**
- Modify: `docs/deployments/kong-gateway-integration.md`
- Modify: `docs/gateway-tool-traffic-boundaries.md`
- Modify: `README.md` if it references the old direct gateway path
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Update docs**

Document workflow-only chat path and Kong-fronted ai-gateway-service deployment.

- [ ] **Step 2: Verify**

Run: `rg "ai-gateway-kong|workflow-only|Kong" docs README.md`

Expected: relevant references found.

- [ ] **Step 3: Mark OpenSpec task 7.4 complete**

Change `- [ ] 7.4` to `- [x] 7.4`.

## Task 7.5: Full Verification

Maps to OpenSpec: 7.5

**Files:**
- Modify: `openspec/changes/switch-ai-traffic-to-kong-gateway/tasks.md`

- [ ] **Step 1: Run focused regression suite**

Run:

```powershell
pytest -q `
  backend/tests/unit/test_schemas.py `
  backend/tests/e2e/test_chat_api.py `
  backend/tests/agent/test_agent.py `
  backend/tests/unit/test_tools.py `
  backend/tests/e2e/test_gateway_integration.py `
  backend/tests/unit/test_kong_manifests.py `
  backend/tests/unit/test_workflows.py `
  backend/tests/unit/test_financial_playbooks.py `
  backend/tests/unit/test_synthetic_specialist_data.py
```

Expected: PASS or documented skips only.

- [ ] **Step 2: Run OpenSpec validation**

Run: `openspec validate switch-ai-traffic-to-kong-gateway`

Expected: `Change 'switch-ai-traffic-to-kong-gateway' is valid`.

- [ ] **Step 3: Mark OpenSpec task 7.5 complete**

Change `- [ ] 7.5` to `- [x] 7.5`.

---

## Self-Review

- Spec coverage: Every OpenSpec task from 1.1 through 7.5 has a matching plan task with the same number.
- Placeholder scan: The plan intentionally uses concrete file paths, commands, expected behavior, and specific snippets. Any implementation-time uncertainty is called out as a decision point rather than hidden behind TODO language.
- Type consistency: `agent_mode` converges to `Literal["workflow"]`, `OPENAI_BASE_URL` converges to `http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1`, and Kong upstream converges to `http://ai-gateway.ai-gateway.svc.cluster.local`.

