# RAG Retrieve Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AI Market Studio retrieve grounded knowledge from `POST /retrieve` and let its configured application LLM generate the final answer.

**Architecture:** Keep `RAGConnector.query_research()` as the stable application-facing method, but change its HTTP contract from the answer-generating `/query` endpoint to retrieval-only `/retrieve`. Normalize retrieved chunks into the existing `type: "rag"` payload, preserve source metadata for the UI and exports, and pass bounded evidence excerpts into the agent's tool message so the application LLM can produce the grounded response.

**Tech Stack:** Python 3.12, FastAPI, httpx, OpenAI-compatible chat completions, pytest, respx, Ruff.

## Global Constraints

- Do not call a generative model inside `ai-rag-service` for AI Market Studio research queries.
- Continue using the `research_reports` collection when `document_type="research_report"`.
- Preserve the existing top-level RAG payload fields (`type`, `answer`, `sources`, optional `error`) so UI and PDF consumers continue working; `answer` is empty in retrieval mode, while a new `evidence` field retains all matched chunks before source-name deduplication.
- Limit evidence sent to the application LLM to five chunks and 1,200 characters per chunk.
- Keep the existing `/query` endpoint available in `ai-rag-service`; this change affects only AI Market Studio.
- Record the pre-existing live OpenAI E2E failure separately; do not weaken feature tests to accommodate it.

---

### Task 1: Switch the RAG connector to retrieval-only responses

**Files:**
- Modify: `backend/connectors/rag_connector.py`
- Test: `backend/tests/unit/test_rag_connector.py`

**Interfaces:**
- Consumes: `POST /retrieve` with `query`, `top_k`, optional `collection`, and optional `filters`.
- Produces: `RAGConnector.query_research(question: str, document_type: str | None = None) -> dict[str, Any]` returning `{"type": "rag", "answer": "", "sources": [...]}`.

- [ ] **Step 1: Write failing connector tests**

Add tests that mock `POST /retrieve`, assert the outgoing JSON contract, and verify nested lifecycle metadata is normalized:

```python
request = respx_mock.post("/retrieve").mock(
    return_value=httpx.Response(
        200,
        json={"results": [{
            "content": "Policy evidence",
            "document_id": "doc-123",
            "chunk_id": "doc-123:0",
            "metadata": {"title": "Policy", "type": "research_report"},
            "score": 0.91,
            "source_url": "https://example.test/policy",
        }]},
    )
)
result = await connector.query_research("market trends", "research_report")
assert request.calls[0].request.json() == {
    "query": "market trends",
    "top_k": 5,
    "collection": "research_reports",
}
assert result["answer"] == ""
assert result["sources"][0]["content"] == "Policy evidence"
```

- [ ] **Step 2: Run the connector test and verify RED**

Run:

```powershell
$env:OPENAI_API_KEY='test'; $env:EXCHANGERATE_API_KEY='test'; uv run pytest backend/tests/unit/test_rag_connector.py -q
```

Expected: FAIL because the connector still calls `/query` and expects `answer`/`sources`.

- [ ] **Step 3: Implement retrieval normalization**

Update `query_research()` to send:

```python
payload: dict[str, Any] = {"query": question, "top_k": 5}
if document_type == "research_report":
    payload["collection"] = "research_reports"
elif document_type and document_type != "general":
    payload["filters"] = {"document_type": document_type}
```

Normalize each `results` item by flattening `metadata.title`, retaining `content`, `chunk_id`, `score`, `source_url`, and the complete metadata dict. Return deduplicated documents in `sources`, all matched chunks in `evidence`, an empty `answer` for compatibility, and keep the existing error payload behavior.

- [ ] **Step 4: Run the connector tests and verify GREEN**

Run the Task 1 command again. Expected: all connector tests pass.

### Task 2: Give the application LLM bounded RAG evidence

**Files:**
- Modify: `backend/agent/agent.py`
- Test: `backend/tests/agent/test_agent.py`

**Interfaces:**
- Consumes: normalized RAG `sources` for citations and non-deduplicated `evidence` chunks containing `name`, `content`, `score`, and `source_url`.
- Produces: a compact tool message containing `sources` plus an `evidence` list.

- [ ] **Step 1: Write a failing agent test**

Create an `AsyncMock` RAG connector returning a source with distinctive evidence text. Run the two-turn agent loop and assert the second chat-completion call includes that evidence in the `role="tool"` message, while content longer than 1,200 characters is truncated.

- [ ] **Step 2: Run the agent test and verify RED**

Run:

```powershell
$env:OPENAI_API_KEY='test'; $env:EXCHANGERATE_API_KEY='test'; uv run pytest backend/tests/agent/test_agent.py -q
```

Expected: FAIL because `_summarise_tool_result()` currently sends only source names.

- [ ] **Step 3: Implement the bounded evidence summary**

For `type == "rag"`, return:

```python
{
    "type": "rag",
    "sources": [source names],
    "evidence": [
        {
            "title": source name,
            "content": source content truncated to 1_200 characters,
            "score": source score,
            "source_url": source URL,
        }
        for the first five sources with content
    ],
}
```

- [ ] **Step 4: Run the agent tests and verify GREEN**

Run the Task 2 command again. Expected: all agent tests pass.

### Task 3: Update downstream synthesis and end-to-end contracts

**Files:**
- Modify: `backend/agents/research_synthesizer.py`
- Modify: `backend/tests/unit/test_research_synthesizer.py`
- Modify: `backend/tests/e2e/test_rag_integration.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: retrieval-mode RAG sources rather than a generated `answer`.
- Produces: deterministic research evidence summaries for multi-source workflows, normalized source data for API/UI consumers, and accurate integration documentation.

- [ ] **Step 1: Write failing synthesizer and E2E tests**

Change the RAG synthesizer fixture to contain `sources: [{"name": "Fed Outlook", "content": "The Federal Reserve..."}]` and assert the evidence appears in the insight. Change the E2E mock to `POST /retrieve` with lifecycle `results`, assert `answer == ""`, and assert normalized content/title are returned.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
$env:OPENAI_API_KEY='test'; $env:EXCHANGERATE_API_KEY='test'; $env:RAG_SERVICE_URL='http://34.10.130.210'; uv run pytest backend/tests/unit/test_research_synthesizer.py backend/tests/e2e/test_rag_integration.py -q
```

Expected: FAIL because the synthesizer expects `answer` and the E2E test still reflects `/query`.

- [ ] **Step 3: Implement source-based synthesis and documentation**

Update `_analyze_rag_source()` to select the first non-empty source `content`, truncate it to 150 characters using the existing behavior, and prefix it with `Research evidence:`. Update README references so they state that `RAGConnector` calls `POST {RAG_SERVICE_URL}/retrieve` and AI Market Studio's configured LLM generates the final answer.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Task 3 command again. Expected: all focused tests pass.

### Task 4: Run the AI application quality gate

**Files:**
- Verify all modified files.

**Interfaces:**
- Consumes: the complete feature diff.
- Produces: lint and test evidence suitable for review.

- [ ] **Step 1: Run Ruff**

```powershell
uv run --with ruff==0.8.0 ruff check backend
```

Expected: `All checks passed!`

- [ ] **Step 2: Run the repository test selection with non-secret test configuration**

Run the repository-owned test selection with `OPENAI_API_KEY`, `EXCHANGERATE_API_KEY`, and `RAG_SERVICE_URL` set to test values. Expected: all tests except the pre-existing `test_sub_agent_orchestration_workflow` live-API test pass.

- [ ] **Step 3: Verify the diff and working tree**

```powershell
git diff --check
git status -sb
```

Expected: no whitespace errors and only planned files are modified.
