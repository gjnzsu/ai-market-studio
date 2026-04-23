# Retrospective: Duplicate Sources Fix

## Issue
RAG service was returning duplicate source filenames in the UI:
```
Sources:
Monthly Foreign Exchange Outlook.pdf
Monthly Foreign Exchange Outlook.pdf
FX_Outlook_2026_Nov_2025.pdf
FX_Outlook_2026_Nov_2025.pdf
FX_Outlook_2026_Nov_2025.pdf
```

## Root Cause Analysis

### Why the duplicates occurred
The RAG service (`ai-rag-service`) returns multiple chunks from the same document by design - this is correct behavior for retrieval systems. When a query matches multiple sections of the same PDF, all relevant chunks are returned with their metadata.

### Why the first fix failed

**Initial approach (WRONG):**
- Fixed deduplication in the **frontend** (`ai-market-studio-ui/index.html`)
- Added: `const uniqueSources = [...new Set(data.data.sources.map(s => s.name || s))]`
- Deployed only the frontend

**Why it didn't work:**
- The backend (`ai-market-studio/backend/connectors/rag_connector.py`) was still sending duplicate sources in the API response
- The frontend fix was correct, but it was applied AFTER the backend had already normalized and sent the data
- The backend's `_normalize_sources` method was creating a new dict for each source without checking for duplicates

**Correct approach (FIXED):**
- Fixed deduplication in the **backend** (`rag_connector.py`)
- Added a `seen_names` set to track unique source names
- Only append sources that haven't been seen before
- Deployed the backend

## What We Learned

### 1. **Fix at the source, not the symptom**
- The frontend was displaying what the backend sent
- Fixing the frontend masked the problem but didn't solve it at the source
- The backend should send clean, deduplicated data

### 2. **Understand the data flow**
```
RAG Service → Backend (rag_connector.py) → Frontend (index.html)
              ↑ FIX HERE                    ✗ Not here
```

### 3. **Test the API directly**
- Should have tested the backend API response directly: `curl http://35.224.3.54/...`
- Would have immediately seen that the backend was sending duplicates
- Browser testing alone didn't reveal where the problem originated

### 4. **Microservices debugging requires layer-by-layer analysis**
- With 3 services (RAG → Backend → Frontend), need to test each layer
- Don't assume the problem is in the UI just because that's where it's visible

## Prevention Measures

### Immediate
1. ✅ Backend deduplication implemented in `rag_connector.py`
2. ✅ Frontend deduplication kept as defense-in-depth
3. ✅ Both services deployed

### Future
1. **Add API integration tests** that verify source deduplication
2. **Add unit tests** for `_normalize_sources` method
3. **Document data flow** in architecture diagrams
4. **Test each layer independently** before blaming the UI

## Code Changes

### Backend Fix (ai-market-studio/backend/connectors/rag_connector.py)
```python
@staticmethod
def _normalize_sources(raw_sources: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_sources, list):
        return []

    normalized_sources: list[dict[str, Any]] = []
    seen_names: set[str] = set()  # ← Added this

    for source in raw_sources:
        if isinstance(source, dict):
            source_name = (
                source.get("title")
                or source.get("document_id")
                or source.get("name")
                or "Unknown source"
            )
            # Deduplicate by source name
            if source_name not in seen_names:  # ← Added this check
                seen_names.add(source_name)
                normalized_sources.append({"name": source_name, **source})
        else:
            source_str = str(source)
            if source_str not in seen_names:  # ← Added this check
                seen_names.add(source_str)
                normalized_sources.append({"name": source_str})
    return normalized_sources
```

### Frontend Fix (ai-market-studio-ui/index.html) - Defense in depth
```javascript
// Deduplicate sources by name
const uniqueSources = [...new Set(data.data.sources.map(s => s.name || s))];
const sourcesHtml = uniqueSources.map(s => `<li>${s}</li>`).join('');
```

## Timeline
- **First attempt**: Fixed frontend only → Didn't work
- **Root cause identified**: Backend was sending duplicates
- **Second attempt**: Fixed backend → ✅ Success

## Key Takeaway
**Always trace the data from its source.** In a microservices architecture, fixing symptoms in the UI without understanding the upstream data flow leads to incomplete solutions.
