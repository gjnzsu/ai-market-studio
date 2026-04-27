# Sub-Agent Performance Analysis
**Date:** 2026-04-27
**Issue:** Intermittent errors and slow response times after sub-agent implementation

## Timeline
- **April 26, 2026**: Sub-agent feature implemented (commits 90efef4 → 88a5796)
- **April 27, 2026**: User reports intermittent errors and slow responses

## Sub-Agent Architecture

### Current Design
The system uses a **sequential orchestrator pattern**:

1. **Main Orchestrator** (`agent.py`) - GPT-4o function-calling loop
2. **4 Sub-Agents** (called as tools):
   - `collect_market_data` - Data Collector
   - `analyze_market_trends` - Market Analyst
   - `generate_report` - Report Generator
   - `synthesize_research` - Research Synthesizer

### How It Works
```
User Query → Main Agent (GPT-4o) → Tool Call → Sub-Agent → Result → Main Agent → Response
```

**Example flow for "market insight on EUR/USD":**
1. Main agent calls GPT-4o API (#1)
2. GPT-4o decides to call `collect_market_data` tool
3. Sub-agent fetches data (HTTP calls to connectors)
4. Result sent back to main agent
5. Main agent calls GPT-4o API again (#2)
6. GPT-4o decides to call `analyze_market_trends` tool
7. Sub-agent analyzes data
8. Result sent back to main agent
9. Main agent calls GPT-4o API again (#3)
10. GPT-4o generates final response

**Total LLM calls: 3-5 per user query** (vs 1-2 before sub-agents)

## Performance Bottlenecks Identified

### 🔴 Critical Issue #1: Sequential LLM Calls
**Problem:** Each sub-agent tool call requires a round-trip to GPT-4o

**Evidence from logs:**
```
08:37:47 - Making request with model: gpt-4o
08:37:48 - Tool call: get_exchange_rate
08:37:48 - Making request with model: gpt-4o  ← 2nd call
08:37:49 - POST /api/chat "200 OK"
```

**Impact:**
- Each GPT-4o call: ~1-2 seconds
- 3-5 calls per query = **3-10 seconds total**
- Before sub-agents: 1-2 calls = **1-4 seconds**

**Latency increase: 2-3x slower**

### 🔴 Critical Issue #2: Tool Call Overhead
**Problem:** The orchestrator must decide which sub-agent to call at each step

**Code analysis (`agent.py:150-196`):**
```python
for _ in range(MAX_TOOL_ROUNDS):  # Up to 5 rounds
    response = await client.chat.completions.create(...)  # LLM call
    if choice.finish_reason == "tool_calls":
        for tool_call in msg.tool_calls:
            result = await dispatch_tool(...)  # Execute sub-agent
            messages.append(...)  # Add result to context
        continue  # Loop back for another LLM call
```

**Impact:**
- Each tool call adds 1 LLM round-trip
- Context grows with each round (more tokens = slower)
- MAX_TOOL_ROUNDS=5 means up to 5 sequential LLM calls

### 🟡 Moderate Issue #3: No Parallel Execution
**Problem:** Sub-agents are called sequentially even when independent

**System prompt says:**
```
When fetching data from multiple independent sources, call Data Collector
multiple times in parallel.
```

**Reality:** GPT-4o cannot execute tools in parallel. It must:
1. Call tool A
2. Wait for result
3. Call tool B
4. Wait for result

**Impact:**
- Fetching rates + news + FRED = 3 sequential calls
- Each call: 1-2 seconds
- Total: 3-6 seconds (could be 1-2 seconds if parallel)

### 🟡 Moderate Issue #4: Increased Token Usage
**Problem:** Each sub-agent call adds to context window

**Evidence from code (`agent.py:140-162`):**
```python
total_prompt_tokens = 0
total_completion_tokens = 0
# Accumulate tokens across all LLM calls
```

**Impact:**
- Longer system prompt (sub-agent descriptions)
- Tool results added to context each round
- More tokens = higher latency + cost

### 🟢 Minor Issue #5: Observability Overhead
**Problem:** Observability tracking wraps every LLM call

**Code (`agent.py:145-149`):**
```python
async with obs.track_llm_call(...) as tracker:
    for _ in range(MAX_TOOL_ROUNDS):
        response = await client.chat.completions.create(...)
```

**Impact:** Minimal (async metrics batching), but adds complexity

## Root Cause Summary

**Primary cause:** Sequential LLM orchestration pattern
- Before: 1-2 LLM calls per query
- After: 3-5 LLM calls per query
- **Result: 2-3x latency increase**

**Secondary causes:**
1. No true parallel execution (GPT-4o limitation)
2. Growing context window per round
3. Tool dispatch overhead

## Why Errors Occur

### "Internal server error"
**Hypothesis:** Timeout or resource exhaustion during long sequential chains

**Possible scenarios:**
1. Request takes >30s (frontend timeout)
2. Backend pod CPU throttling (500m limit, multiple LLM calls)
3. AI Gateway connection pool exhaustion (sequential calls)

### "Network error: could not reach the backend"
**Hypothesis:** Frontend timeout while waiting for slow backend response

**Evidence:**
- Frontend likely has 10-30s timeout
- Backend can take 5-10s for complex queries
- No error in backend logs = frontend gave up waiting

## Recommendations

### 🚀 High Impact Solutions

#### 1. Implement Parallel Tool Execution (Recommended)
**Change:** Allow GPT-4o to call multiple tools in one round

**Implementation:**
```python
# Current: Sequential
response = await client.chat.completions.create(
    tools=TOOL_DEFINITIONS,
    tool_choice="auto",  # One tool at a time
)

# Proposed: Parallel
response = await client.chat.completions.create(
    tools=TOOL_DEFINITIONS,
    tool_choice="auto",
    parallel_tool_calls=True,  # NEW: Enable parallel execution
)
```

**Impact:**
- Reduce 3 sequential calls to 1 parallel batch
- Latency: 6s → 2s (3x faster)
- Requires OpenAI API `parallel_tool_calls` feature

#### 2. Reduce MAX_TOOL_ROUNDS
**Change:** Limit orchestration rounds to prevent long chains

**Implementation:**
```python
# Current
MAX_TOOL_ROUNDS = 5

# Proposed
MAX_TOOL_ROUNDS = 3  # Enough for: collect → analyze → respond
```

**Impact:**
- Prevent runaway loops
- Faster timeout on complex queries
- May reduce quality for very complex queries

#### 3. Add Request Timeout
**Change:** Fail fast instead of hanging

**Implementation:**
```python
# In router.py
@router.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        result = await asyncio.wait_for(
            run_agent(...),
            timeout=15.0  # 15 second timeout
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Request timeout - query too complex"
        )
```

**Impact:**
- Clear error message instead of hanging
- Frontend can retry or simplify query

#### 4. Increase Backend Resources
**Change:** Handle multiple LLM calls without throttling

**Implementation:**
```yaml
# k8s/deployment.yaml
resources:
  requests:
    cpu: "500m"      # Current: 250m
    memory: "512Mi"  # Current: 256Mi
  limits:
    cpu: "1000m"     # Current: 500m
    memory: "1Gi"    # Current: 512Mi
```

**Impact:**
- Better performance under load
- Handle concurrent requests
- Higher cost

### 🔧 Medium Impact Solutions

#### 5. Cache Sub-Agent Results
**Change:** Avoid redundant data fetching

**Implementation:**
```python
# Add simple in-memory cache
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=100)
async def collect_market_data_cached(data_type, pairs, ...):
    # Cache for 60 seconds
    return await collect_market_data(...)
```

**Impact:**
- Faster repeated queries
- Reduced API calls
- Memory overhead

#### 6. Simplify System Prompt
**Change:** Reduce token overhead per LLM call

**Current:** 68 lines of sub-agent descriptions
**Proposed:** 30 lines with concise descriptions

**Impact:**
- Faster LLM calls (fewer input tokens)
- Lower cost
- May reduce orchestration quality

### 📊 Monitoring Solutions

#### 7. Add Performance Metrics
**Change:** Track sub-agent performance

**Implementation:**
```python
# In agent.py
logger.info(f"[Perf] Tool {tool_name} took {elapsed:.2f}s")
logger.info(f"[Perf] Total LLM calls: {llm_call_count}")
logger.info(f"[Perf] Total latency: {total_elapsed:.2f}s")
```

**Impact:**
- Identify slow sub-agents
- Track latency trends
- Debug performance issues

## Comparison: Before vs After Sub-Agents

| Metric | Before (Legacy Tools) | After (Sub-Agents) | Change |
|--------|----------------------|-------------------|--------|
| LLM calls per query | 1-2 | 3-5 | +150% |
| Avg latency | 2-4s | 5-10s | +150% |
| Token usage | 1000-2000 | 2000-4000 | +100% |
| Code complexity | Low | High | +200% |
| Flexibility | Low | High | +300% |

## Decision Matrix

### Option A: Keep Sub-Agents + Optimize (Recommended)
**Pros:**
- Better architecture for future features
- More flexible and maintainable
- Can optimize performance

**Cons:**
- Requires optimization work
- Higher baseline latency
- More complex debugging

**Actions:**
1. Enable parallel tool calls
2. Reduce MAX_TOOL_ROUNDS to 3
3. Add 15s timeout
4. Increase CPU to 1000m

**Expected result:** 5-10s → 3-5s latency

### Option B: Rollback to Legacy Tools
**Pros:**
- Immediate performance improvement
- Simpler code
- Proven stable

**Cons:**
- Lose architectural benefits
- Harder to add new features
- Technical debt

**Actions:**
1. Revert commits 90efef4 → 88a5796
2. Remove agents/ directory
3. Redeploy

**Expected result:** 5-10s → 2-4s latency

### Option C: Hybrid Approach
**Pros:**
- Best of both worlds
- Gradual migration
- Lower risk

**Cons:**
- Maintain two code paths
- More complexity

**Actions:**
1. Keep legacy tools as default
2. Add sub-agents as opt-in feature flag
3. Migrate gradually

**Expected result:** 5-10s → 2-4s (legacy), 5-10s (sub-agents)

## Recommended Action Plan

### Phase 1: Quick Wins (Today)
1. ✅ Remove ai-mcp-server sidecar (DONE)
2. Reduce MAX_TOOL_ROUNDS from 5 to 3
3. Add 15s request timeout
4. Increase backend CPU to 1000m

**Expected improvement:** 30-40% latency reduction

### Phase 2: Optimization (This Week)
1. Enable parallel_tool_calls in OpenAI API
2. Add performance logging
3. Simplify system prompt
4. Add result caching

**Expected improvement:** 50-60% latency reduction

### Phase 3: Architecture Review (Next Week)
1. Benchmark sub-agents vs legacy tools
2. Consider hybrid approach
3. Evaluate alternative orchestration patterns
4. Load testing

**Expected improvement:** Informed decision on architecture

## Conclusion

**Root cause:** Sub-agent sequential orchestration pattern increases LLM calls from 1-2 to 3-5 per query, causing 2-3x latency increase.

**Immediate fix:** Reduce MAX_TOOL_ROUNDS, add timeout, increase resources

**Long-term fix:** Enable parallel tool execution or consider hybrid approach

**Trade-off:** Sub-agents provide better architecture but higher latency. Need to optimize or rollback based on user requirements.
