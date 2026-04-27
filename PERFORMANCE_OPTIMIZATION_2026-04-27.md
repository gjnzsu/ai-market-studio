# Performance Optimization Deployment
**Date:** 2026-04-27
**Issue:** Sub-agent sequential orchestration causing 2-3x latency increase

## Changes Applied

### 1. ✅ Removed ai-mcp-server Sidecar
**File:** `k8s/deployment.yaml`
**Impact:** Freed 100-200m CPU, 128-256Mi memory

### 2. ✅ Reduced MAX_TOOL_ROUNDS
**File:** `backend/agent/agent.py`
**Change:** `MAX_TOOL_ROUNDS = 5` → `MAX_TOOL_ROUNDS = 3`
**Impact:** Prevents long sequential chains, faster timeout on complex queries

### 3. ✅ Added Request Timeout
**File:** `backend/router.py`
**Change:** Added 20-second timeout with `asyncio.wait_for()`
**Impact:** Fail fast instead of hanging, clear error messages

### 4. ✅ Increased Backend Resources
**File:** `k8s/deployment.yaml`
**Changes:**
- CPU request: 250m → 500m
- CPU limit: 500m → 1000m
- Memory request: 256Mi → 512Mi
- Memory limit: 512Mi → 1Gi

**Impact:** Better performance under load, handle multiple LLM calls without throttling

## Deployment Status

**Deployed:** 2026-04-27
**Pod:** `ai-market-studio-5db6bbd4d8-42xwn`
**Status:** Running (1/1)
**Age:** 60s

## Expected Performance Improvement

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Max LLM rounds | 5 | 3 | -40% |
| Request timeout | None | 20s | Fail fast |
| CPU limit | 500m | 1000m | +100% |
| Memory limit | 512Mi | 1Gi | +100% |
| Sidecar overhead | 200m CPU | 0 | -100% |

**Expected latency reduction:** 30-40%

## Testing Checklist

- [ ] Test simple query (e.g., "What's EUR/USD rate?")
- [ ] Test complex query (e.g., "Market insight on EUR/USD with news and FRED data")
- [ ] Verify timeout works (should fail at 20s, not hang)
- [ ] Check backend logs for performance metrics
- [ ] Monitor error rate in frontend

## Next Steps (If Issues Persist)

### Phase 2: Advanced Optimizations
1. Enable `parallel_tool_calls=True` in OpenAI API
2. Add result caching for repeated queries
3. Simplify system prompt (reduce token overhead)
4. Add performance logging

### Phase 3: Architecture Decision
1. Benchmark sub-agents vs legacy tools
2. Consider hybrid approach (feature flag)
3. Evaluate rollback to legacy tools if needed

## Rollback Plan

If performance doesn't improve:

```bash
# Revert to previous deployment
kubectl rollout undo deployment/ai-market-studio -n default

# Or revert commits
cd C:/SourceCode/ai-market-studio
git revert HEAD~3..HEAD
```

## Monitoring

**Watch logs:**
```bash
kubectl logs -f -n default -l app=ai-market-studio
```

**Check resource usage:**
```bash
kubectl top pods -n default -l app=ai-market-studio
```

**Test endpoint:**
```bash
curl -X POST http://35.224.3.54/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is EUR/USD rate?","history":[]}'
```

## Files Modified

1. `backend/agent/agent.py` - Reduced MAX_TOOL_ROUNDS
2. `backend/router.py` - Added timeout
3. `k8s/deployment.yaml` - Increased resources, removed sidecar

## Related Documents

- `SUB_AGENT_PERFORMANCE_ANALYSIS.md` - Detailed root cause analysis
- `TROUBLESHOOTING_2026-04-27.md` - Initial investigation report
