# Retrospectives

Post-mortem analysis and lessons learned from incidents and fixes.

## 2026-04-03 - Network Error Resolution
**File:** `2026-04-03-network-error-resolution.md`

Root cause: `env-config.html` was HTML being loaded as JavaScript, causing silent failures and fallback to localhost:8000.

**Key Lessons:**
- Always test in actual browser environment, not just curl/API tests
- File extensions matter - use `.js` for JavaScript files
- Implement cache-control headers to prevent caching issues
- Create verification scripts to catch build problems before deployment

## 2026-04-04 - Duplicate Sources Fix
**File:** `2026-04-04-duplicate-sources-fix.md`

Root cause: RAG service returns multiple chunks from same document (correct behavior), but backend wasn't deduplicating before sending to frontend.

**Key Lessons:**
- Fix at the source, not the symptom - backend should send clean data
- In microservices, trace data flow from origin: RAG Service → Backend → Frontend
- Test each layer independently
- Defense-in-depth: kept frontend deduplication as secondary safeguard

## Action Items
**File:** `action-items-2026-04-03.md`

Follow-up tasks from the network error incident to prevent recurrence.
