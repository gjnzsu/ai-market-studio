# Fix: Cost Metrics Not Showing in Grafana

**Date:** 2026-04-27
**Issue:** Cost metrics not appearing in Grafana dashboards
**Status:** 🔧 IN PROGRESS

---

## Root Cause Analysis

### Investigation Results

**Symptom:** Grafana dashboards show no LLM cost or token usage data for ai-market-studio.

**Root Cause:** The observability SDK was disabled on 2026-04-26 (commit `1d0ac47`) with the message "Temporarily disabled for Cloud Build deployment".

**Why it was disabled:**
- Cloud Build couldn't access the local SDK path: `file:///c:/SourceCode/ai-sre-observability/sdk`
- The Dockerfile tried to COPY from parent directory, which wasn't in build context
- Quick fix was to comment out SDK imports and initialization

**Impact:**
- ✅ ai-market-studio backend works normally
- ❌ No metrics sent to ai-sre-observability service
- ❌ Prometheus has no LLM cost data to scrape
- ❌ Grafana dashboards are empty

---

## Architecture Review

**How observability works:**

```
ai-market-studio (instrumented with SDK)
    ↓ @track_llm_call decorator wraps agent loop
    ↓ Accumulates tokens across all LLM calls
    ↓ SDK batches metrics every 5 seconds
    ↓ POST /ingest
ai-sre-observability service
    ↓ Calculates cost (tokens × pricing)
    ↓ Updates Prometheus metrics
    ↓ Exposes /metrics endpoint
Prometheus
    ↓ Scrapes every 15 seconds
    ↓ Stores time-series data
Grafana
    ↓ Queries Prometheus
    ↓ Displays dashboards
```

**Current state:**
- ✅ ai-sre-observability service: Running
- ✅ Prometheus: Running, scraping observability service
- ✅ Grafana: Running, dashboards configured
- ❌ ai-market-studio: SDK disabled, no metrics sent

---

## Solution

**Strategy:** Install SDK from GitHub repo instead of local path, re-enable all instrumentation.

### Files Changed

**1. `backend/runtime.txt`**
```diff
+ git+https://github.com/gjnzsu/ai-sre-observability.git#subdirectory=sdk
```

**2. `backend/agent/agent.py`**
```diff
- # Temporarily disabled for Cloud Build deployment
- # from ai_sre_observability import get_client
+ from ai_sre_observability import get_client

- # Get observability client (graceful degradation) - temporarily disabled
- obs = None
- # try:
- #     obs = get_client()
- # except RuntimeError:
- #     obs = None
+ # Get observability client (graceful degradation)
+ try:
+     obs = get_client()
+ except RuntimeError:
+     obs = None
+     logger.warning("Observability not initialized, skipping metrics")
```

**3. `backend/main.py`**
```diff
- # Temporarily disabled for Cloud Build deployment
- # from ai_sre_observability import setup_observability
+ from ai_sre_observability import setup_observability

- # Initialize observability - temporarily disabled for Cloud Build
- # observability_url = os.getenv(...)
- # try:
- #     setup_observability(...)
+ # Initialize observability
+ observability_url = os.getenv(
+     "OBSERVABILITY_URL",
+     "http://ai-sre-observability.default.svc.cluster.local:8080"
+ )
+ try:
+     setup_observability(
+         service_name="ai-market-studio",
+         observability_url=observability_url,
+         batch_interval=5.0,
+         timeout=5.0
+     )
```

---

## Deployment

**Build:**
```bash
cd ai-market-studio
gcloud builds submit --tag gcr.io/gen-lang-client-0896070179/ai-market-studio:latest
```

**Deploy:**
```bash
kubectl rollout restart deployment/ai-market-studio -n default
kubectl rollout status deployment/ai-market-studio -n default
```

**Verify:**
```bash
# Check logs for observability initialization
kubectl logs -n default deployment/ai-market-studio --tail=50 | grep -i observability

# Wait 30 seconds, then check metrics
curl -s http://34.118.229.175:8080/metrics | grep llm_

# Check Grafana dashboard
# http://136.114.77.0 (admin / newpassword123)
```

---

## Expected Results

After deployment and a few test queries:

**Prometheus metrics:**
```prometheus
llm_requests_total{service="ai-market-studio",status="success"}
llm_tokens_total{service="ai-market-studio",token_type="prompt"}
llm_tokens_total{service="ai-market-studio",token_type="completion"}
llm_cost_usd_total{service="ai-market-studio",model="gpt-4o"}
llm_request_duration_seconds_bucket{service="ai-market-studio"}
```

**Grafana dashboards:**
- LLM Cost & Usage: Shows cost per query (~$0.0072 USD)
- Service Overview: Shows request rates and success rates
- Request Tracing: Shows latency distribution

---

## Testing Plan

1. **Deploy and verify startup:**
   ```bash
   kubectl logs -n default deployment/ai-market-studio --tail=20
   # Should see: "Observability initialized: http://ai-sre-observability..."
   ```

2. **Send test query:**
   ```bash
   curl -X POST http://35.224.3.54/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "What is EUR/USD?"}'
   ```

3. **Wait 30 seconds** (for SDK batching + Prometheus scrape)

4. **Check metrics:**
   ```bash
   curl -s http://34.118.229.175:8080/metrics | grep llm_requests_total
   ```

5. **Open Grafana:**
   - URL: http://136.114.77.0
   - Login: admin / newpassword123
   - Dashboard: "LLM Cost & Usage"
   - Should see data points for ai-market-studio

---

## Rollback Plan

If issues occur:

```bash
# Revert to previous commit
cd ai-market-studio
git revert HEAD
gcloud builds submit --tag gcr.io/gen-lang-client-0896070179/ai-market-studio:latest
kubectl rollout restart deployment/ai-market-studio
```

Or manually disable SDK again:
```bash
# Comment out SDK imports and initialization
# Rebuild and redeploy
```

---

## Related Documentation

- Original integration: `docs/deployments/2026-04-23-observability-integration.md`
- Observability platform: `C:\SourceCode\ai-sre-observability\README.md`
- SDK documentation: `C:\SourceCode\ai-sre-observability\sdk\README.md`

---

## Status

- [x] Root cause identified
- [x] Solution designed
- [x] Code changes made
- [ ] Build completed
- [ ] Deployment completed
- [ ] Metrics verified
- [ ] Grafana dashboards verified

**Next:** Wait for build to complete, then deploy and verify.
