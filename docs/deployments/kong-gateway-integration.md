# Kong Gateway Integration

AI Market Studio routes model-provider traffic through an independent Kong Gateway workload in GKE. Kong is not a sidecar; it runs as its own Deployment and forwards requests to the existing AI Gateway service.

## Route Contract

Canonical traffic path:

```text
ai-market-studio -> ai-gateway-kong -> ai-gateway -> model provider
```

Canonical AI Market Studio base URL:

```text
http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1
```

Kong upstream target:

```text
http://ai-gateway.ai-gateway.svc.cluster.local
```

Supported routes through `ai-gateway-kong`:

| Route | Purpose |
| --- | --- |
| `/v1/chat/completions` | Chat completion requests forwarded to AI Gateway. |
| `/v1/models` | Model listing forwarded to AI Gateway. |
| `/health` | Liveness check forwarded to AI Gateway. |
| `/readiness` | Readiness check forwarded to AI Gateway. |

Required request headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` for JSON request bodies. |
| `X-Request-ID` | Caller-provided correlation ID. Kong generates one when absent. |
| `X-Consumer-Service` | `ai-market-studio`. |

Timeout and error categories:

| Category | Meaning |
| --- | --- |
| Kong connection timeout | Kong cannot connect to `ai-gateway.ai-gateway.svc.cluster.local`. |
| Kong read timeout | Kong connected but AI Gateway did not respond before the proxy timeout. |
| Rate limited | Kong rate-limiting plugin returns `429` before forwarding upstream. |
| Upstream error | AI Gateway or the model provider returns `4xx` or `5xx`. |
| Client request error | AI Market Studio sends invalid JSON, missing headers, or unsupported paths. |

Rollback changes `OPENAI_BASE_URL` back to the previous AI Gateway target. Rollback does not restore legacy orchestration behavior or any removed runtime/schema code paths.

## Rollback

Rollback is a routing configuration change only. It points AI Market Studio at the previous OpenAI-compatible AI Gateway service while keeping workflow-only orchestration in place.

```powershell
kubectl patch configmap ai-market-studio-config `
  --type merge `
  -p '{"data":{"OPENAI_BASE_URL":"http://ai-gateway.ai-gateway.svc.cluster.local/v1"}}'
kubectl rollout restart deployment/ai-market-studio -n ai-market-studio
kubectl rollout status deployment/ai-market-studio -n ai-market-studio
```

Do not re-enable legacy orchestration as part of rollback.

## Deploy

Apply the Kong manifests:

```powershell
kubectl apply -f k8s/kong-config.yaml
kubectl apply -f k8s/kong-deployment.yaml
kubectl apply -f k8s/kong-service.yaml
kubectl rollout status deployment/ai-gateway-kong -n ai-gateway
kubectl apply -f k8s/configmap.yaml
kubectl rollout restart deployment/ai-market-studio -n ai-market-studio
kubectl rollout status deployment/ai-market-studio -n ai-market-studio
```

## Validate

Run an in-cluster curl pod and verify each supported route through `ai-gateway-kong`:

```powershell
kubectl run ai-gateway-kong-curl -n ai-gateway --rm -i --restart=Never --image=curlimages/curl -- `
  curl -sS -H "X-Request-ID: kong-health-check" -H "X-Consumer-Service: ai-market-studio" `
  http://ai-gateway-kong.ai-gateway.svc.cluster.local/health

kubectl run ai-gateway-kong-curl -n ai-gateway --rm -i --restart=Never --image=curlimages/curl -- `
  curl -sS -H "X-Request-ID: kong-readiness-check" -H "X-Consumer-Service: ai-market-studio" `
  http://ai-gateway-kong.ai-gateway.svc.cluster.local/readiness

kubectl run ai-gateway-kong-curl -n ai-gateway --rm -i --restart=Never --image=curlimages/curl -- `
  curl -sS -H "X-Request-ID: kong-models-check" -H "X-Consumer-Service: ai-market-studio" `
  http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1/models

kubectl run ai-gateway-kong-curl -n ai-gateway --rm -i --restart=Never --image=curlimages/curl -- `
  curl -sS -X POST `
  -H "Content-Type: application/json" `
  -H "X-Request-ID: kong-chat-check" `
  -H "X-Consumer-Service: ai-market-studio" `
  -d '{"model":"gpt-5.4","messages":[{"role":"user","content":"health check"}]}' `
  http://ai-gateway-kong.ai-gateway.svc.cluster.local/v1/chat/completions
```

Local file checks:

```powershell
Test-Path docs/deployments/kong-gateway-integration.md
rg "ai-gateway-kong.ai-gateway.svc.cluster.local/v1" docs k8s
rg "/health|/readiness|/v1/models|/v1/chat/completions" docs/deployments/kong-gateway-integration.md
```
