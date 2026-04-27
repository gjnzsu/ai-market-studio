# Bug Fix: Internal Server Error on Combined Queries

**Date:** 2026-04-27
**Issue:** Internal server error when combining USD/HKD rate query with internal research report
**Status:** ✅ FIXED

---

## Problem

When users submitted queries combining multiple data sources (e.g., "based on the latest USD/HKD rate and internal research report, generate next month's trend"), the backend returned HTTP 500 Internal Server Error.

**User Query Example:**
```
"I would like to base on the latest usd/hkd rate and the internal research report,
to generate the next one month rate trend."
```

---

## Root Cause Analysis

### Phase 1: Investigation

**Error from logs:**
```
ERROR backend.router — Unexpected error in /chat: cannot import name 'analyze_market_trends'
from 'backend.agents' (/app/backend/agents/__init__.py)

Traceback:
  File "/app/backend/agent/agent.py", line 232, in run_agent
    result = await dispatch_tool(tool_name, tool_args, ...)
  File "/app/backend/agent/tools.py", line 596, in dispatch_tool
    from backend.agents import analyze_market_trends
ImportError: cannot import name 'analyze_market_trends' from 'backend.agents'
```

**Root Cause:**
The multi-agent system was partially implemented but not properly exported. The `backend/agents/__init__.py` only exported `collect_market_data`, but the tool dispatcher tried to import three additional functions:
- `analyze_market_trends` (from `market_analyst.py`)
- `generate_report` (from `report_generator.py`)
- `synthesize_research` (from `research_synthesizer.py`)

### Phase 2: Pattern Analysis

**Files affected:**
- `backend/agents/__init__.py` - Missing exports
- `backend/agents/market_analyst.py` - Function exists but not exported
- `backend/agents/report_generator.py` - Function exists but not exported
- `backend/agents/research_synthesizer.py` - Function exists but not exported
- `backend/agent/tools.py` - Imports all four functions

**Why combined queries triggered this:**
When the agent received a complex query requiring multiple data sources, it attempted to:
1. Call `collect_market_data` to fetch rates ✅
2. Call `get_internal_research` to fetch RAG data ✅
3. Call `analyze_market_trends` to synthesize results ❌ (ImportError)

Simple queries only used step 1-2, so they worked fine.

---

## Solution

### Files Changed

**1. `backend/agents/__init__.py`**

**Before:**
```python
from backend.agents.data_collector import collect_market_data

__all__ = [
    "collect_market_data",
]
```

**After:**
```python
from backend.agents.data_collector import collect_market_data
from backend.agents.market_analyst import analyze_market_trends
from backend.agents.report_generator import generate_report
from backend.agents.research_synthesizer import synthesize_research

__all__ = [
    "collect_market_data",
    "analyze_market_trends",
    "generate_report",
    "synthesize_research",
]
```

### Test Coverage

**New test file:** `backend/tests/unit/test_agents_imports.py`

```python
def test_all_agents_importable():
    """Verify all agent functions can be imported from backend.agents."""
    from backend.agents import (
        collect_market_data,
        analyze_market_trends,
        generate_report,
        synthesize_research
    )

    assert callable(collect_market_data)
    assert callable(analyze_market_trends)
    assert callable(generate_report)
    assert callable(synthesize_research)
```

**Test result:** ✅ All tests pass

---

## Deployment

**Build:**
- Image: `gcr.io/gen-lang-client-0896070179/ai-market-studio:latest`
- Build ID: `dd823d5a-529f-4cb5-9623-bc80b55060ca`
- Status: SUCCESS
- Duration: 38 seconds

**Deployment:**
```bash
kubectl rollout restart deployment/ai-market-studio -n default
kubectl rollout status deployment/ai-market-studio -n default
# deployment "ai-market-studio" successfully rolled out
```

**Verification:**
- New pods started successfully
- No import errors in logs
- Backend API: http://35.224.3.54
- Frontend UI: http://136.116.205.168

---

## Impact

**Before fix:**
- ❌ Combined queries (rate + research) → HTTP 500
- ✅ Simple queries (rate only) → Works
- ✅ Simple queries (research only) → Works

**After fix:**
- ✅ Combined queries (rate + research) → Works
- ✅ Simple queries (rate only) → Works
- ✅ Simple queries (research only) → Works

---

## Prevention

**Added safeguards:**
1. Unit test for agent imports (`test_agents_imports.py`)
2. This test will catch future export issues immediately

**Lesson learned:**
When implementing multi-agent systems, ensure all agent functions are properly exported in `__init__.py` before they are referenced in tool dispatchers.

---

## Related Files

- `backend/agents/__init__.py` - Fixed exports
- `backend/agents/market_analyst.py` - Contains `analyze_market_trends`
- `backend/agents/report_generator.py` - Contains `generate_report`
- `backend/agents/research_synthesizer.py` - Contains `synthesize_research`
- `backend/agent/tools.py` - Tool dispatcher that imports agents
- `backend/tests/unit/test_agents_imports.py` - New test coverage

---

## Commit

```bash
git add backend/agents/__init__.py backend/tests/unit/test_agents_imports.py
git commit -m "fix: export all agent functions to fix combined query errors

- Add analyze_market_trends, generate_report, synthesize_research to __init__.py
- Fixes ImportError when agent tries to synthesize multi-source data
- Add unit test to prevent future export issues
- Resolves HTTP 500 on combined queries (e.g., rate + research)
"
```
