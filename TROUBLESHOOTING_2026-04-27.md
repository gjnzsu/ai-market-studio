# Troubleshooting Report: Backend Errors & Performance Issues
**Date:** 2026-04-27

## Issues Reported
1. Intermittent "Error: Internal server error" on frontend
2. "Network error: could not reach the backend" messages
3. Slow response times from backend

## Root Cause Analysis

### Finding 1: Unnecessary Sidecar Container
**Issue:** The `ai-mcp-server` sidecar container was running alongside the main backend container but was not being used.

**Evidence:**
- Pod had 2/2 containers (ai-market-studio + ai-mcp-server)
- ai-mcp-server consumed 100m CPU request, 200m CPU limit, 128Mi-256Mi memory
- According to memory notes, ai-mcp-server is "reference implementation only, NOT deployed"

**Impact:**
- Wasted resources (CPU/memory)
- Potential pod scheduling delays
- Unnecessary container startup time

**Resolution:** ✅ Removed ai-mcp-server sidecar from deployment.yaml

### Finding 2: AI Gateway Already Scaled Down
**Status:** ai-gateway was already running with 1 replica (not 2 as suspected)

**Evidence:**
```
NAME         READY   UP-TO-DATE   AVAILABLE   AGE
ai-gateway   1/1     1            1           17d
```

**Resource Usage:**
- CPU: 3m (very low)
- Memory: 152Mi
- No errors in logs

**Conclusion:** AI Gateway is NOT the bottleneck.

### Finding 3: Backend Logs Show Normal Operation
**Evidence from logs:**
- All requests returning 200 OK
- LLM calls completing successfully (1-3 seconds per call)
- Gateway communication working: `POST http://ai-gateway.ai-gateway.svc.cluster.local/v1/chat/completions "HTTP/1.1 200 OK"`
- Observability metrics being sent successfully

**Suspicious Activity:**
- Multiple `/docs` endpoint hits (likely health checks or bots)
- Attempted access to `/.env` and `/.git/credentials` (security scanning attempts - blocked with 404)

## Actions Taken

### 1. Removed ai-mcp-server Sidecar ✅
**File:** `k8s/deployment.yaml`
**Change:** Removed lines 49-71 (entire ai-mcp-server container definition)
**Deployment:** Applied and rolled out successfully
**Result:** Pod now runs 1/1 container instead of 2/2

**Before:**
```
ai-market-studio-8d4d5f597-fv69h   2/2     Running
```

**After:**
```
ai-market-studio-b78f79c7d-t7ql6   1/1     Running
```

### 2. Verified AI Gateway Configuration ✅
- Already running 1 replica (no scaling needed)
- Resource usage is minimal
- No errors in logs

## Recommendations

### Immediate Actions
1. **Monitor frontend errors** - Check browser console for specific error messages
2. **Test backend directly** - Use `curl http://35.224.3.54/api/chat` to isolate frontend vs backend issues
3. **Check frontend logs** - Verify nginx logs on frontend pods for connection errors

### Performance Optimization
1. **Increase backend resources** if needed:
   - Current: 250m CPU request, 500m limit
   - Consider: 500m request, 1000m limit for better performance

2. **Add connection pooling** - Verify httpx client in backend uses connection pooling for ai-gateway calls

3. **Add request timeout monitoring** - Track slow requests (>5s) separately

### Security
1. **Rate limiting** - Consider adding rate limiting to prevent abuse (many `/docs` hits)
2. **Block security scanners** - Add nginx rules to block common scanning patterns

## Next Steps
1. Monitor backend performance after sidecar removal
2. If errors persist, investigate frontend → backend connectivity
3. Consider adding request tracing to identify slow endpoints

## Resource Savings
**Removed:**
- CPU request: 100m
- CPU limit: 200m
- Memory request: 128Mi
- Memory limit: 256Mi

**Impact:** Faster pod startup, reduced resource consumption, simpler deployment
