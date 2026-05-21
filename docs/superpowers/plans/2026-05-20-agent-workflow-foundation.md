# Agent Workflow Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `agent-workflow-foundation` OpenSpec change by adding explicit chat orchestration modes, mode-specific tool sets, intent-level market workflows, workflow guardrails, and tests.

**Architecture:** Keep legacy chat orchestration as the default path. Add an opt-in workflow path that exposes customer-intent tools only, backed by internal workflow helpers and existing connector/agent internals. Replace model-facing `generate_market_insight` with `generate_market_briefing` while preserving `/api/chat` request/response compatibility.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, OpenAI chat tool calling, pytest, OpenSpec.

---

## OpenSpec Alignment

| Plan area | OpenSpec tasks covered |
|---|---|
| Task 1: Mode selection foundation | 1.1, 1.2, 1.3, 1.4, 1.5 |
| Task 2: Tool set separation | 2.1, 2.2, 2.3, 2.4, 2.5, 2.6 |
| Task 3: Workflow implementation | 3.1, 3.2, 3.3, 3.4, 3.5, 3.6 |
| Task 4: Market insight replacement | 4.1, 4.2, 4.3, 4.4 |
| Task 5: Guardrails and observability | 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2 |
| Task 6: Verification and docs | 6.3, 6.4, 6.5 |

## Assumptions and Defaults

- Chat request field: `agent_mode`.
- Allowed values: `"legacy"` and `"workflow"`.
- Default: `"legacy"`.
- Config flag: `enable_agent_workflow_mode: bool = False`.
- Disabled workflow handling: workflow mode remains disabled by default and is rejected clearly when selected, without defining a new public API response contract in this plan.
- Workflow request timeout config: `agent_workflow_timeout_seconds: float = 20.0`.
- Workflow orchestration round limit config: `agent_workflow_max_rounds: int = 2`.
- Legacy model-facing tools exclude `generate_market_insight` after replacement.
- Workflow model-facing tools are only `collect_market_context`, `analyze_market_context`, and `generate_market_briefing`.
- The unrelated untracked `ingest_research_reports.py` file must remain untouched.

## Known Baseline Issue

- Targeted baseline command:

```powershell
$env:PYTHONPATH='.'; uv run pytest backend\tests\unit\test_schemas.py backend\tests\unit\test_tools.py backend\tests\agent\test_agent.py backend\tests\e2e\test_chat_api.py -q
```

- Current baseline result before implementation: `44 passed, 2 failed`.
- Failing tests:
  - `backend\tests\unit\test_tools.py::test_dispatch_get_interest_rate`
  - `backend\tests\unit\test_tools.py::test_dispatch_get_interest_rate_missing_series_id`
- Root cause: these direct unit tests call `dispatch_tool("get_interest_rate", ...)` without passing a `fred_connector`, so they bypass the real app path where `main.py` creates `app.state.fred_connector` from `FRED_API_KEY` and `router.py` passes it into `run_agent`.
- Scope decision: proceed with `agent-workflow-foundation` implementation while treating these as known stale baseline tests. After this change, add a follow-up cleanup to fix the FRED unit tests by injecting a mock FRED connector and asserting missing `series_id` validation independently from connector availability.

## File Structure

- Modify `backend/config.py`: workflow enablement, timeout, and step-limit settings.
- Modify `backend/models.py`: `AgentMode` literal and optional `agent_mode` on `ChatRequest`.
- Modify `backend/router.py`: mode validation, workflow-disabled guard, timeout selection, pass mode into `run_agent`.
- Modify `backend/agent/agent.py`: mode-aware prompt/tool selection and workflow round limit.
- Modify `backend/agent/tools.py`: split tool definitions, add workflow tool schemas, route workflow tool dispatch, remove `generate_market_insight` from approved tool sets.
- Create `backend/agent/workflows.py`: intent-level workflow functions and workflow result helpers.
- Modify tests under `backend/tests/unit`, `backend/tests/e2e`, and `backend/tests/agent`.
- Modify `openspec/changes/agent-workflow-foundation/tasks.md`: mark tasks complete as implementation progresses.
- Update `README.md` with the workflow configuration settings added by this change.

---

### Task 1: Mode Selection Foundation

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/models.py`
- Modify: `backend/router.py`
- Modify: `backend/agent/agent.py`
- Test: `backend/tests/unit/test_schemas.py`
- Test: `backend/tests/e2e/test_chat_api.py`
- Test: `backend/tests/agent/test_agent.py`

- [ ] **Step 1: Write schema tests for `agent_mode` default and validation**

Add these tests to `backend/tests/unit/test_schemas.py` near existing `ChatRequest` tests:

```python
def test_chat_request_defaults_to_legacy_agent_mode():
    req = ChatRequest(message="What is EUR/USD?")
    assert req.agent_mode == "legacy"


def test_chat_request_accepts_workflow_agent_mode():
    req = ChatRequest(message="Brief EUR/USD", agent_mode="workflow")
    assert req.agent_mode == "workflow"


def test_chat_request_rejects_unknown_agent_mode():
    with pytest.raises(ValidationError):
        ChatRequest(message="Brief EUR/USD", agent_mode="multi_agent")
```

- [ ] **Step 2: Run schema tests and verify failure**

Run:

```powershell
uv run pytest backend\tests\unit\test_schemas.py -q
```

Expected: failures because `ChatRequest` has no `agent_mode` field validation yet.

- [ ] **Step 3: Implement config and model fields**

Update `backend/config.py`:

```python
    enable_agent_workflow_mode: bool = False
    agent_workflow_timeout_seconds: float = 20.0
    agent_workflow_max_rounds: int = 2
```

Update imports and `ChatRequest` in `backend/models.py`:

```python
AgentMode = Literal["legacy", "workflow"]


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []
    agent_mode: AgentMode = "legacy"
```

- [ ] **Step 4: Run schema tests and verify pass**

Run:

```powershell
uv run pytest backend\tests\unit\test_schemas.py -q
```

Expected: all tests in `test_schemas.py` pass.

- [ ] **Step 5: Write route tests for disabled workflow guard and legacy pass-through**

Add to `backend/tests/e2e/test_chat_api.py`:

```python
def test_chat_workflow_mode_disabled_is_rejected(app_client, monkeypatch):
    monkeypatch.setattr("backend.router.settings.enable_agent_workflow_mode", False)

    resp = app_client.post(
        "/api/chat",
        json={"message": "Brief EUR/USD", "agent_mode": "workflow"},
    )

    assert resp.is_error
    assert "workflow" in resp.text.lower()


def test_chat_default_mode_passes_legacy_to_run_agent(app_client, monkeypatch):
    captured = {}

    async def fake_run_agent(**kwargs):
        captured.update(kwargs)
        return {"reply": "ok", "data": None, "tool_used": None}

    monkeypatch.setattr("backend.router.run_agent", fake_run_agent)

    resp = app_client.post("/api/chat", json={"message": "What is EUR/USD?"})

    assert resp.status_code == 200
    assert captured["agent_mode"] == "legacy"
    assert set(resp.json().keys()) == {"reply", "data", "tool_used"}


def test_chat_explicit_legacy_mode_passes_legacy_to_run_agent(app_client, monkeypatch):
    captured = {}

    async def fake_run_agent(**kwargs):
        captured.update(kwargs)
        return {"reply": "ok", "data": None, "tool_used": None}

    monkeypatch.setattr("backend.router.run_agent", fake_run_agent)

    resp = app_client.post(
        "/api/chat",
        json={"message": "What is EUR/USD?", "agent_mode": "legacy"},
    )

    assert resp.status_code == 200
    assert captured["agent_mode"] == "legacy"
    assert set(resp.json().keys()) == {"reply", "data", "tool_used"}


def test_chat_workflow_mode_keeps_response_shape_when_enabled(app_client, monkeypatch):
    captured = {}
    monkeypatch.setattr("backend.router.settings.enable_agent_workflow_mode", True)

    async def fake_run_agent(**kwargs):
        captured.update(kwargs)
        return {
            "reply": "workflow ok",
            "data": {"type": "market_briefing"},
            "tool_used": "generate_market_briefing",
        }

    monkeypatch.setattr("backend.router.run_agent", fake_run_agent)

    resp = app_client.post(
        "/api/chat",
        json={"message": "Brief EUR/USD", "agent_mode": "workflow"},
    )

    assert resp.status_code == 200
    assert captured["agent_mode"] == "workflow"
    assert set(resp.json().keys()) == {"reply", "data", "tool_used"}
```

- [ ] **Step 6: Run route tests and verify failure**

Run:

```powershell
uv run pytest backend\tests\e2e\test_chat_api.py::test_chat_workflow_mode_disabled_is_rejected backend\tests\e2e\test_chat_api.py::test_chat_default_mode_passes_legacy_to_run_agent backend\tests\e2e\test_chat_api.py::test_chat_explicit_legacy_mode_passes_legacy_to_run_agent backend\tests\e2e\test_chat_api.py::test_chat_workflow_mode_keeps_response_shape_when_enabled -q
```

Expected: failures because router does not validate/pass `agent_mode` yet.

- [ ] **Step 7: Implement router mode handling**

Update `backend/router.py` imports:

```python
from backend.config import settings
```

Update `chat()` before calling `run_agent`:

```python
    def _workflow_mode_disabled_error() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent workflow mode is disabled.",
        )

    if body.agent_mode == "workflow" and not settings.enable_agent_workflow_mode:
        raise _workflow_mode_disabled_error()

    timeout_seconds = (
        settings.agent_workflow_timeout_seconds
        if body.agent_mode == "workflow"
        else 20.0
    )
```

This uses the existing FastAPI route error mechanism as an internal guard. The helper keeps the disabled-mode decision local so a later Contract Refinement step can change the exact client-facing status/detail without touching the mode-selection flow.

Pass mode into `run_agent` and use `timeout_seconds`:

```python
                agent_mode=body.agent_mode,
```

```python
            timeout=timeout_seconds
```

- [ ] **Step 8: Extend `run_agent` signature**

Update `backend/agent/agent.py`:

```python
from typing import Literal, Optional

AgentMode = Literal["legacy", "workflow"]
```

Add parameter:

```python
    agent_mode: AgentMode = "legacy",
```

For this task, keep behavior otherwise unchanged.

- [ ] **Step 9: Run route tests and verify pass**

Run:

```powershell
uv run pytest backend\tests\e2e\test_chat_api.py::test_chat_workflow_mode_disabled_is_rejected backend\tests\e2e\test_chat_api.py::test_chat_default_mode_passes_legacy_to_run_agent backend\tests\e2e\test_chat_api.py::test_chat_explicit_legacy_mode_passes_legacy_to_run_agent backend\tests\e2e\test_chat_api.py::test_chat_workflow_mode_keeps_response_shape_when_enabled -q
```

Expected: both tests pass.

- [ ] **Step 10: Mark OpenSpec tasks 1.1 through 1.5 complete**

Update `openspec/changes/agent-workflow-foundation/tasks.md`:

```markdown
- [x] 1.1 Add a disabled-by-default configuration setting for agent workflow availability.
- [x] 1.2 Extend the chat request model with an optional orchestration mode field that defaults to legacy behavior when omitted.
- [x] 1.3 Update the chat route to reject workflow mode with a clear client-facing error when workflow mode is disabled.
- [x] 1.4 Pass the selected orchestration mode from the chat route into the agent runtime.
- [x] 1.5 Add tests proving existing chat requests without a mode still use legacy orchestration and keep the existing response shape.
```

- [ ] **Step 11: Commit mode selection foundation**

Run:

```powershell
git add -- backend\config.py backend\models.py backend\router.py backend\agent\agent.py backend\tests\unit\test_schemas.py backend\tests\e2e\test_chat_api.py openspec\changes\agent-workflow-foundation\tasks.md
git commit -m "feat: add agent workflow mode selection"
```

---

### Task 2: Mode-Specific Tool Sets

**Files:**
- Modify: `backend/agent/tools.py`
- Modify: `backend/agent/agent.py`
- Test: `backend/tests/unit/test_tools.py`
- Test: `backend/tests/agent/test_agent.py`

- [ ] **Step 1: Write tool grouping tests**

Replace `test_tool_definitions_are_valid` in `backend/tests/unit/test_tools.py` with:

```python
from backend.agent.tools import (
    LEGACY_TOOL_DEFINITIONS,
    WORKFLOW_TOOL_DEFINITIONS,
    TOOL_DEFINITIONS,
    get_tool_definitions,
    dispatch_tool,
    AgentError,
)


def _tool_names(tools):
    return [tool["function"]["name"] for tool in tools]


def test_legacy_tool_definitions_exclude_workflow_and_deprecated_tools():
    names = _tool_names(LEGACY_TOOL_DEFINITIONS)
    assert "get_exchange_rate" in names
    assert "get_fx_news" in names
    assert "generate_market_insight" not in names
    assert "collect_market_data" not in names
    assert "analyze_market_trends" not in names
    assert "generate_report" not in names
    assert "synthesize_research" not in names
    assert "collect_market_context" not in names


def test_workflow_tool_definitions_expose_only_intent_tools():
    names = _tool_names(WORKFLOW_TOOL_DEFINITIONS)
    assert names == [
        "collect_market_context",
        "analyze_market_context",
        "generate_market_briefing",
    ]


def test_get_tool_definitions_selects_by_agent_mode():
    assert get_tool_definitions("legacy") == LEGACY_TOOL_DEFINITIONS
    assert get_tool_definitions("workflow") == WORKFLOW_TOOL_DEFINITIONS


def test_tool_definitions_alias_remains_legacy_compatible():
    assert TOOL_DEFINITIONS == LEGACY_TOOL_DEFINITIONS
```

- [ ] **Step 2: Run tool grouping tests and verify failure**

Run:

```powershell
uv run pytest backend\tests\unit\test_tools.py::test_legacy_tool_definitions_exclude_workflow_and_deprecated_tools backend\tests\unit\test_tools.py::test_workflow_tool_definitions_expose_only_intent_tools backend\tests\unit\test_tools.py::test_get_tool_definitions_selects_by_agent_mode backend\tests\unit\test_tools.py::test_tool_definitions_alias_remains_legacy_compatible -q
```

Expected: import/name failures because grouped definitions do not exist.

- [ ] **Step 3: Split tool definitions**

Refactor `backend/agent/tools.py`:

```python
LEGACY_TOOL_DEFINITIONS = [
    # existing approved legacy tools only:
    # get_exchange_rate, get_exchange_rates, get_historical_rates,
    # list_supported_currencies, generate_dashboard, get_fx_news,
    # get_internal_research, get_interest_rate, analyze_fx_economic_correlation
]

WORKFLOW_TOOL_DEFINITIONS = [
    # collect_market_context, analyze_market_context, generate_market_briefing
]

TOOL_DEFINITIONS = LEGACY_TOOL_DEFINITIONS


def get_tool_definitions(agent_mode: str) -> list[dict[str, Any]]:
    if agent_mode == "workflow":
        return WORKFLOW_TOOL_DEFINITIONS
    return LEGACY_TOOL_DEFINITIONS
```

Workflow tool schemas:

```python
{
    "type": "function",
    "function": {
        "name": "collect_market_context",
        "description": "Collect requested FX rates, news, FRED indicators, and research context without analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "pairs": {"type": "array", "items": {"type": "string"}},
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["rates", "news", "fred", "research"]},
                },
                "days": {"type": "integer"},
                "fred_series_ids": {"type": "array", "items": {"type": "string"}},
                "query": {"type": "string"},
            },
            "required": [],
        },
    },
}
```

Add this exact workflow analysis schema:

```python
{
    "type": "function",
    "function": {
        "name": "analyze_market_context",
        "description": "Analyze collected or supplied FX market context without generating a full briefing.",
        "parameters": {
            "type": "object",
            "properties": {
                "pairs": {"type": "array", "items": {"type": "string"}},
                "analysis_type": {
                    "type": "string",
                    "enum": ["trend", "volatility", "economic_relationship", "general"],
                },
                "days": {"type": "integer"},
                "context": {"type": "object"},
            },
            "required": [],
        },
    },
}
```

Add this exact workflow briefing schema:

```python
{
    "type": "function",
    "function": {
        "name": "generate_market_briefing",
        "description": "Generate a structured market briefing by coordinating context collection, analysis, and synthesis internally.",
        "parameters": {
            "type": "object",
            "properties": {
                "pairs": {"type": "array", "items": {"type": "string"}},
                "focus": {"type": "string"},
                "include_news": {"type": "boolean"},
                "include_fred": {"type": "boolean"},
                "include_research": {"type": "boolean"},
                "fred_series_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["pairs"],
        },
    },
}
```

- [ ] **Step 4: Write agent test for mode-specific tool set**

Add to `backend/tests/agent/test_agent.py`:

```python
@pytest.mark.asyncio
async def test_agent_uses_workflow_tool_set_when_workflow_mode_selected():
    connector = MockConnector()
    final_response = make_response(content="ok", finish_reason="stop")
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=final_response)

    await run_agent(
        message="Brief EUR/USD",
        connector=connector,
        client=mock_client,
        agent_mode="workflow",
    )

    tools = mock_client.chat.completions.create.call_args.kwargs["tools"]
    names = [tool["function"]["name"] for tool in tools]
    assert names == [
        "collect_market_context",
        "analyze_market_context",
        "generate_market_briefing",
    ]
```

- [ ] **Step 5: Run agent tool-set test and verify failure**

Run:

```powershell
uv run pytest backend\tests\agent\test_agent.py::test_agent_uses_workflow_tool_set_when_workflow_mode_selected -q
```

Expected: failure because `run_agent` still sends `TOOL_DEFINITIONS`.

- [ ] **Step 6: Update `run_agent` to select tools by mode**

Update import:

```python
from backend.agent.tools import get_tool_definitions, dispatch_tool, AgentError
```

Before the loop:

```python
    tool_definitions = get_tool_definitions(agent_mode)
```

Replace both `tools=TOOL_DEFINITIONS` occurrences:

```python
                    tools=tool_definitions,
```

- [ ] **Step 7: Run tool and agent tests**

Run:

```powershell
uv run pytest backend\tests\unit\test_tools.py backend\tests\agent\test_agent.py -q
```

Expected: failures only where tests still assert old `generate_market_insight` behavior. Update those in Task 4, not here unless they block import-level validation.

- [ ] **Step 8: Mark OpenSpec tasks 2.1 through 2.6 complete after tests pass**

Update `tasks.md` checkboxes for `2.1` through `2.6`.

- [ ] **Step 9: Commit tool set separation**

Run:

```powershell
git add -- backend\agent\tools.py backend\agent\agent.py backend\tests\unit\test_tools.py backend\tests\agent\test_agent.py openspec\changes\agent-workflow-foundation\tasks.md
git commit -m "feat: split agent tool sets by mode"
```

---

### Task 3: Intent-Level Workflow Layer

**Files:**
- Create: `backend/agent/workflows.py`
- Modify: `backend/agent/tools.py`
- Test: `backend/tests/unit/test_workflows.py`
- Test: `backend/tests/unit/test_tools.py`

- [ ] **Step 1: Write workflow unit tests**

Create `backend/tests/unit/test_workflows.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agent.workflows import (
    collect_market_context,
    analyze_market_context,
    generate_market_briefing,
)


@pytest.mark.asyncio
async def test_collect_market_context_returns_data_only():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }

    result = await collect_market_context(
        pairs=["EUR/USD"],
        sources=["rates"],
        connector=connector,
    )

    assert result["type"] == "market_context"
    assert result["context"]["rates"][0]["rate"] == 1.08
    assert "analysis" not in result
    assert "briefing" not in result


@pytest.mark.asyncio
async def test_analyze_market_context_returns_analysis_not_briefing():
    context = {
        "type": "market_context",
        "context": {
            "rates": [
                {"date": "2026-05-19", "rate": 1.07},
                {"date": "2026-05-20", "rate": 1.08},
            ]
        },
        "warnings": [],
    }

    result = await analyze_market_context(
        context=context,
        analysis_type="trend",
    )

    assert result["type"] == "market_analysis"
    assert "analysis" in result
    assert "briefing" not in result


@pytest.mark.asyncio
async def test_generate_market_briefing_coordinates_context_and_analysis():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }
    news_connector = MagicMock()
    news_connector.get_fx_news.return_value = []

    result = await generate_market_briefing(
        pairs=["EUR/USD"],
        connector=connector,
        news_connector=news_connector,
    )

    assert result["type"] == "market_briefing"
    assert "context" in result
    assert "analysis" in result
    assert "briefing" in result
```

- [ ] **Step 2: Run workflow tests and verify failure**

Run:

```powershell
uv run pytest backend\tests\unit\test_workflows.py -q
```

Expected: import failure because `backend.agent.workflows` does not exist.

- [ ] **Step 3: Implement workflow module**

Create `backend/agent/workflows.py` with:

```python
import logging
import time
from typing import Any, Optional

from backend.connectors.base import MarketDataConnector
from backend.connectors.news_connector import NewsConnectorBase
from backend.agents.market_analyst import analyze_market_trends

logger = logging.getLogger(__name__)


def _split_pair(pair: str) -> tuple[str, str]:
    parts = pair.upper().replace("-", "/").split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid currency pair: {pair}")
    return parts[0], parts[1]


async def collect_market_context(
    pairs: Optional[list[str]] = None,
    sources: Optional[list[str]] = None,
    days: Optional[int] = None,
    fred_series_ids: Optional[list[str]] = None,
    query: Optional[str] = None,
    connector: Optional[MarketDataConnector] = None,
    news_connector: Optional[NewsConnectorBase] = None,
    fred_connector=None,
    rag_connector=None,
) -> dict[str, Any]:
    selected = sources or ["rates"]
    context: dict[str, Any] = {}
    warnings: list[dict[str, str]] = []

    if "rates" in selected:
        if connector is None:
            raise ValueError("connector is required for rates context")
        rate_results = []
        for pair in pairs or []:
            base, target = _split_pair(pair)
            rate_results.append(await connector.get_exchange_rate(base=base, target=target))
        context["rates"] = rate_results

    if "news" in selected:
        if news_connector is None:
            warnings.append({"source": "news", "error": "News connector not available"})
        else:
            context["news"] = news_connector.get_fx_news(query=query, max_items=5)

    if "fred" in selected:
        if fred_connector is None:
            warnings.append({"source": "fred", "error": "FRED connector not available"})
        else:
            fred_results = []
            for series_id in fred_series_ids or ["DFF"]:
                fred_results.append((await fred_connector.get_current_rate(series_id=series_id)).model_dump())
            context["fred"] = fred_results

    if "research" in selected:
        if rag_connector is None:
            warnings.append({"source": "research", "error": "RAG connector not available"})
        else:
            context["research"] = await rag_connector.query_research(question=query or "FX market outlook")

    return {
        "type": "market_context",
        "context": context,
        "warnings": warnings,
        "metadata": {"sources": selected, "pairs": pairs or []},
    }
```

Add `analyze_market_context` and `generate_market_briefing`:

```python
async def analyze_market_context(
    context: Optional[dict[str, Any]] = None,
    pairs: Optional[list[str]] = None,
    analysis_type: str = "trend",
    days: Optional[int] = None,
    connector: Optional[MarketDataConnector] = None,
    **connectors,
) -> dict[str, Any]:
    market_context = context
    if market_context is None:
        market_context = await collect_market_context(
            pairs=pairs,
            sources=["rates"],
            days=days,
            connector=connector,
            **connectors,
        )
    analysis_input = {"data": market_context.get("context", {}).get("rates", [])}
    analysis = await analyze_market_trends(data=analysis_input, analysis_type=analysis_type)
    return {
        "type": "market_analysis",
        "context": market_context,
        "analysis": analysis,
        "warnings": market_context.get("warnings", []),
    }


async def generate_market_briefing(
    pairs: list[str],
    focus: Optional[str] = None,
    include_news: bool = True,
    include_fred: bool = False,
    include_research: bool = True,
    fred_series_ids: Optional[list[str]] = None,
    connector: Optional[MarketDataConnector] = None,
    news_connector: Optional[NewsConnectorBase] = None,
    fred_connector=None,
    rag_connector=None,
) -> dict[str, Any]:
    sources = ["rates"]
    if include_news:
        sources.append("news")
    if include_fred:
        sources.append("fred")
    if include_research:
        sources.append("research")

    context = await collect_market_context(
        pairs=pairs,
        sources=sources,
        fred_series_ids=fred_series_ids,
        query=focus or " ".join(pairs),
        connector=connector,
        news_connector=news_connector,
        fred_connector=fred_connector,
        rag_connector=rag_connector,
    )
    analysis = await analyze_market_context(context=context, analysis_type="trend")
    return {
        "type": "market_briefing",
        "pairs": pairs,
        "context": context,
        "analysis": analysis["analysis"],
        "briefing": {
            "summary": "Market briefing context collected and analyzed.",
            "focus": focus,
        },
        "warnings": context.get("warnings", []),
    }
```

- [ ] **Step 4: Route workflow dispatch**

Add to `dispatch_tool` in `backend/agent/tools.py`:

```python
    elif tool_name == "collect_market_context":
        from backend.agent.workflows import collect_market_context
        return await collect_market_context(
            pairs=tool_args.get("pairs"),
            sources=tool_args.get("sources"),
            days=tool_args.get("days"),
            fred_series_ids=tool_args.get("fred_series_ids"),
            query=tool_args.get("query"),
            connector=connector,
            news_connector=news_connector,
            fred_connector=fred_connector,
            rag_connector=rag_connector,
        )
```

Add this `analyze_market_context` dispatch branch:

```python
    elif tool_name == "analyze_market_context":
        from backend.agent.workflows import analyze_market_context
        return await analyze_market_context(
            context=tool_args.get("context"),
            pairs=tool_args.get("pairs"),
            analysis_type=tool_args.get("analysis_type", "general"),
            days=tool_args.get("days"),
            connector=connector,
            news_connector=news_connector,
            fred_connector=fred_connector,
            rag_connector=rag_connector,
        )
```

Add this `generate_market_briefing` dispatch branch:

```python
    elif tool_name == "generate_market_briefing":
        from backend.agent.workflows import generate_market_briefing
        return await generate_market_briefing(
            pairs=tool_args.get("pairs") or [],
            focus=tool_args.get("focus"),
            include_news=tool_args.get("include_news", True),
            include_fred=tool_args.get("include_fred", False),
            include_research=tool_args.get("include_research", True),
            fred_series_ids=tool_args.get("fred_series_ids"),
            connector=connector,
            news_connector=news_connector,
            fred_connector=fred_connector,
            rag_connector=rag_connector,
        )
```

- [ ] **Step 5: Run workflow tests**

Run:

```powershell
uv run pytest backend\tests\unit\test_workflows.py backend\tests\unit\test_tools.py -q
```

Expected: workflow tests pass; update any import assertions in `test_tools.py` to match new tool groups.

- [ ] **Step 6: Mark OpenSpec tasks 3.1 through 3.6 complete**

Update `tasks.md` checkboxes for `3.1` through `3.6`.

- [ ] **Step 7: Commit workflow layer**

Run:

```powershell
git add -- backend\agent\workflows.py backend\agent\tools.py backend\tests\unit\test_workflows.py backend\tests\unit\test_tools.py openspec\changes\agent-workflow-foundation\tasks.md
git commit -m "feat: add intent-level market workflows"
```

---

### Task 4: Market Insight Replacement

**Files:**
- Modify: `backend/agent/agent.py`
- Modify: `backend/agent/tools.py`
- Modify: `backend/tests/unit/test_generate_market_insight_with_rag.py`
- Modify: `backend/tests/unit/test_tools.py`
- Modify: `backend/tests/e2e/test_chat_api.py`

- [ ] **Step 1: Replace old market insight unit tests**

Replace `backend/tests/unit/test_generate_market_insight_with_rag.py` with this workflow briefing test content:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agent.tools import dispatch_tool


@pytest.mark.asyncio
async def test_generate_market_briefing_includes_research_when_available():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }
    news = MagicMock()
    news.get_fx_news.return_value = []
    rag = AsyncMock()
    rag.query_research = AsyncMock(return_value={
        "type": "rag",
        "answer": "EUR/USD outlook is constructive.",
        "sources": [{"name": "Monthly FX Outlook.pdf"}],
    })

    result = await dispatch_tool(
        "generate_market_briefing",
        {"pairs": ["EUR/USD"], "include_research": True},
        connector,
        news_connector=news,
        rag_connector=rag,
    )

    assert result["type"] == "market_briefing"
    assert "research" in result["context"]["context"]
    rag.query_research.assert_called_once()


@pytest.mark.asyncio
async def test_generate_market_insight_is_no_longer_supported():
    with pytest.raises(Exception):
        await dispatch_tool(
            "generate_market_insight",
            {"pairs": ["EUR/USD"]},
            AsyncMock(),
        )
```

- [ ] **Step 2: Run replacement tests and verify failure**

Run:

```powershell
uv run pytest backend\tests\unit\test_generate_market_insight_with_rag.py -q
```

Expected: failure until old dispatch support is removed and briefing dispatch exists.

- [ ] **Step 3: Remove `generate_market_insight` dispatch branch**

In `backend/agent/tools.py`, remove the `elif tool_name == "generate_market_insight":` branch. Do not include it in any approved tool set.

- [ ] **Step 4: Update prompt language**

In `backend/agent/agent.py`, remove legacy `generate_market_insight` prompt references and add workflow prompt text for workflow mode:

```python
LEGACY_SYSTEM_PROMPT = """
You are an AI assistant for AI Market Studio...
...
"""

WORKFLOW_SYSTEM_PROMPT = """
You are an AI assistant for AI Market Studio using intent-level market workflows.
Use collect_market_context for data-only requests, analyze_market_context for analysis,
and generate_market_briefing for market insight, overview, briefing, or synthesis requests.
"""
```

Use selected prompt:

```python
system_prompt = WORKFLOW_SYSTEM_PROMPT if agent_mode == "workflow" else LEGACY_SYSTEM_PROMPT
```

- [ ] **Step 5: Add chat-level insight replacement test**

Add to `backend/tests/agent/test_agent.py`:

```python
@pytest.mark.asyncio
async def test_workflow_mode_can_use_market_briefing_tool_for_insight():
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[make_tool_call("generate_market_briefing", {"pairs": ["EUR/USD"]})],
        finish_reason="tool_calls",
    )
    final_response = make_response(content="EUR/USD briefing ready.", finish_reason="stop")
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=[tool_response, final_response])

    result = await run_agent(
        message="Give me a market insight on EUR/USD",
        connector=connector,
        client=mock_client,
        agent_mode="workflow",
    )

    assert result["tool_used"] == "generate_market_briefing"
    assert result["data"]["type"] == "market_briefing"
```

- [ ] **Step 6: Run agent and tool tests**

Run:

```powershell
uv run pytest backend\tests\agent\test_agent.py backend\tests\unit\test_tools.py backend\tests\unit\test_generate_market_insight_with_rag.py -q
```

Expected: pass after replacement updates.

- [ ] **Step 7: Mark OpenSpec tasks 4.1 through 4.4 complete**

Update `tasks.md` checkboxes for `4.1` through `4.4`.

- [ ] **Step 8: Commit market insight replacement**

Run:

```powershell
git add -- backend\agent\agent.py backend\agent\tools.py backend\tests\agent\test_agent.py backend\tests\unit\test_tools.py backend\tests\unit\test_generate_market_insight_with_rag.py openspec\changes\agent-workflow-foundation\tasks.md
git commit -m "feat: replace market insight with briefing workflow"
```

---

### Task 5: Workflow Guardrails and Observability

**Files:**
- Modify: `backend/agent/agent.py`
- Modify: `backend/agent/workflows.py`
- Modify: `backend/router.py`
- Test: `backend/tests/agent/test_agent.py`
- Test: `backend/tests/unit/test_workflows.py`
- Test: `backend/tests/e2e/test_chat_api.py`

- [ ] **Step 1: Write no-silent-fallback test**

Add to `backend/tests/agent/test_agent.py`:

```python
@pytest.mark.asyncio
async def test_workflow_mode_unknown_tool_does_not_fallback_to_legacy():
    connector = MockConnector()
    tool_response = make_response(
        tool_calls=[make_tool_call("unknown_workflow_tool", {})],
        finish_reason="tool_calls",
    )
    final_response = make_response(content="Could not complete workflow.", finish_reason="stop")
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=[tool_response, final_response])

    result = await run_agent(
        message="Brief EUR/USD",
        connector=connector,
        client=mock_client,
        agent_mode="workflow",
    )

    assert result["tool_used"] is None or result["tool_used"] != "get_exchange_rate"
```

- [ ] **Step 2: Write workflow step-limit test**

Add to `backend/tests/agent/test_agent.py`:

```python
@pytest.mark.asyncio
async def test_workflow_mode_stops_at_configured_step_limit(monkeypatch):
    connector = MockConnector()
    monkeypatch.setattr("backend.agent.agent.settings.agent_workflow_max_rounds", 1)
    tool_response = make_response(
        tool_calls=[make_tool_call("collect_market_context", {"pairs": ["EUR/USD"]})],
        finish_reason="tool_calls",
    )
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=tool_response)

    result = await run_agent(
        message="Keep working on EUR/USD until complete",
        connector=connector,
        client=mock_client,
        agent_mode="workflow",
    )

    assert "too complex" in result["reply"].lower() or "incomplete" in result["reply"].lower()
    assert result["tool_used"] == "collect_market_context"
```

- [ ] **Step 3: Write optional and required source failure tests**

Add to `backend/tests/unit/test_workflows.py`:

```python
@pytest.mark.asyncio
async def test_market_briefing_represents_optional_research_failure():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }
    rag = AsyncMock()
    rag.query_research.side_effect = Exception("RAG down")

    result = await generate_market_briefing(
        pairs=["EUR/USD"],
        connector=connector,
        include_news=False,
        include_fred=False,
        include_research=True,
        rag_connector=rag,
    )

    assert result["type"] == "market_briefing"
    assert any(w["source"] == "research" for w in result["warnings"])


@pytest.mark.asyncio
async def test_market_context_required_rate_failure_is_not_success():
    connector = AsyncMock()
    connector.get_exchange_rate.side_effect = Exception("rates down")

    with pytest.raises(Exception, match="rates down"):
        await collect_market_context(
            pairs=["EUR/USD"],
            sources=["rates"],
            connector=connector,
        )
```

- [ ] **Step 4: Write legacy isolation regression test**

Add to `backend/tests/agent/test_agent.py`:

```python
@pytest.mark.asyncio
async def test_previous_workflow_failure_does_not_alter_later_legacy_tool_set():
    connector = MockConnector()
    workflow_tool_response = make_response(
        tool_calls=[make_tool_call("unknown_workflow_tool", {})],
        finish_reason="tool_calls",
    )
    workflow_final_response = make_response(content="Workflow failed.", finish_reason="stop")
    legacy_final_response = make_response(content="Legacy ok.", finish_reason="stop")
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[workflow_tool_response, workflow_final_response, legacy_final_response]
    )

    await run_agent(
        message="Brief EUR/USD",
        connector=connector,
        client=mock_client,
        agent_mode="workflow",
    )
    await run_agent(
        message="What is EUR/USD?",
        connector=connector,
        client=mock_client,
        agent_mode="legacy",
    )

    legacy_tools = mock_client.chat.completions.create.call_args.kwargs["tools"]
    legacy_names = [tool["function"]["name"] for tool in legacy_tools]
    assert "get_exchange_rate" in legacy_names
    assert "collect_market_context" not in legacy_names
```

- [ ] **Step 5: Run guardrail tests and verify failure**

Run:

```powershell
uv run pytest backend\tests\agent\test_agent.py::test_workflow_mode_unknown_tool_does_not_fallback_to_legacy backend\tests\agent\test_agent.py::test_workflow_mode_stops_at_configured_step_limit backend\tests\agent\test_agent.py::test_previous_workflow_failure_does_not_alter_later_legacy_tool_set backend\tests\unit\test_workflows.py::test_market_briefing_represents_optional_research_failure backend\tests\unit\test_workflows.py::test_market_context_required_rate_failure_is_not_success -q
```

Expected: failures until step-limit responses, tool-set isolation, and optional source warnings are implemented.

- [ ] **Step 6: Implement source warning handling**

In `collect_market_context`, wrap optional `news`, `fred`, and `research` calls in `try/except Exception as e` and append:

```python
warnings.append({"source": "research", "error": str(e)})
```

Keep rates as required when requested; if rates collection fails, raise.

- [ ] **Step 7: Implement workflow round limit in `run_agent`**

In `backend/agent/agent.py`:

```python
    max_rounds = settings.agent_workflow_max_rounds if agent_mode == "workflow" else MAX_TOOL_ROUNDS
    last_tool_result: Optional[dict[str, Any]] = None
    last_tool_name: Optional[str] = None
```

Replace both `for _ in range(MAX_TOOL_ROUNDS):` loops:

```python
            for _ in range(max_rounds):
```

After successful dispatch, record the most recent workflow tool result:

```python
                    last_tool_name = tool_name
                    last_tool_result = result if isinstance(result, dict) else {"result": result}
```

After the loop, return a clear incomplete response when workflow mode exhausts its step limit:

```python
    if agent_mode == "workflow":
        return {
            "reply": "The workflow could not complete within the configured step limit; the request may be too complex or incomplete.",
            "data": last_tool_result,
            "tool_used": last_tool_name,
        }
```

- [ ] **Step 8: Add workflow execution logging**

In `backend/agent/agent.py`, before each LLM call:

```python
logger.info("[Agent] mode=%s model=%s", agent_mode, settings.openai_model)
```

Around dispatch:

```python
logger.info("Tool call: mode=%s tool=%s args=%s", agent_mode, tool_name, tool_args)
```

In `backend/agent/workflows.py`, log workflow start/end with internal units, latency, status, and failure category by wrapping `generate_market_briefing`:

```python
async def _generate_market_briefing_impl(
    pairs: list[str],
    focus: Optional[str],
    include_news: bool,
    include_fred: bool,
    include_research: bool,
    fred_series_ids: Optional[list[str]],
    connector: Optional[MarketDataConnector],
    news_connector: Optional[NewsConnectorBase],
    fred_connector,
    rag_connector,
) -> dict[str, Any]:
    sources = ["rates"]
    if include_news:
        sources.append("news")
    if include_fred:
        sources.append("fred")
    if include_research:
        sources.append("research")

    context = await collect_market_context(
        pairs=pairs,
        sources=sources,
        fred_series_ids=fred_series_ids,
        query=focus or " ".join(pairs),
        connector=connector,
        news_connector=news_connector,
        fred_connector=fred_connector,
        rag_connector=rag_connector,
    )
    analysis = await analyze_market_context(context=context, analysis_type="trend")
    return {
        "type": "market_briefing",
        "pairs": pairs,
        "context": context,
        "analysis": analysis["analysis"],
        "briefing": {
            "summary": "Market briefing context collected and analyzed.",
            "focus": focus,
        },
        "warnings": context.get("warnings", []),
    }
```

Then make `generate_market_briefing` call that helper with logging:

```python
    started_at = time.perf_counter()
    internal_units = ["collect_market_context", "analyze_market_context"]
    logger.info(
        "workflow_start mode=workflow name=generate_market_briefing units=%s pairs=%s",
        internal_units,
        pairs,
    )
    try:
        result = await _generate_market_briefing_impl(
            pairs=pairs,
            focus=focus,
            include_news=include_news,
            include_fred=include_fred,
            include_research=include_research,
            fred_series_ids=fred_series_ids,
            connector=connector,
            news_connector=news_connector,
            fred_connector=fred_connector,
            rag_connector=rag_connector,
        )
        logger.info(
            "workflow_complete mode=workflow name=generate_market_briefing units=%s latency_ms=%.2f status=success failure_category=none",
            internal_units,
            (time.perf_counter() - started_at) * 1000,
        )
        return result
    except Exception:
        logger.exception(
            "workflow_complete mode=workflow name=generate_market_briefing units=%s latency_ms=%.2f status=failure failure_category=exception",
            internal_units,
            (time.perf_counter() - started_at) * 1000,
        )
        raise
```

- [ ] **Step 9: Add timeout route test**

Add to `backend/tests/e2e/test_chat_api.py`:

```python
def test_chat_workflow_timeout_returns_504(app_client, monkeypatch):
    import asyncio

    monkeypatch.setattr("backend.router.settings.enable_agent_workflow_mode", True)
    monkeypatch.setattr("backend.router.settings.agent_workflow_timeout_seconds", 0.001)

    async def slow_run_agent(**kwargs):
        await asyncio.sleep(0.1)
        return {"reply": "late", "data": None, "tool_used": None}

    monkeypatch.setattr("backend.router.run_agent", slow_run_agent)

    resp = app_client.post(
        "/api/chat",
        json={"message": "Brief EUR/USD", "agent_mode": "workflow"},
    )

    assert resp.status_code == 504
```

- [ ] **Step 10: Run guardrail tests**

Run:

```powershell
uv run pytest backend\tests\e2e\test_chat_api.py backend\tests\unit\test_workflows.py backend\tests\agent\test_agent.py -q
```

Expected: pass.

- [ ] **Step 11: Mark OpenSpec tasks 5.1 through 5.6, 6.1, and 6.2 complete**

Update `tasks.md` checkboxes for `5.1` through `5.6`, plus `6.1` and `6.2`.

- [ ] **Step 12: Commit guardrails**

Run:

```powershell
git add -- backend\agent\agent.py backend\agent\workflows.py backend\router.py backend\tests\agent\test_agent.py backend\tests\unit\test_workflows.py backend\tests\e2e\test_chat_api.py openspec\changes\agent-workflow-foundation\tasks.md
git commit -m "feat: add workflow guardrails"
```

---

### Task 6: Verification and Documentation

**Files:**
- Modify: `README.md`
- Modify: `openspec/changes/agent-workflow-foundation/tasks.md`

- [ ] **Step 1: Run targeted tests**

Run:

```powershell
uv run pytest backend\tests\unit\test_schemas.py backend\tests\unit\test_tools.py backend\tests\unit\test_workflows.py backend\tests\agent\test_agent.py backend\tests\e2e\test_chat_api.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run OpenSpec validation**

Run:

```powershell
npx.cmd openspec validate agent-workflow-foundation --type change --strict
```

Expected:

```text
Change 'agent-workflow-foundation' is valid
```

- [ ] **Step 3: Run lint/quality command**

No repo-owned `scripts/quality-check.ps1` exists. Run:

```powershell
uv run ruff check backend tests
```

Expected: no lint errors. If `uv run ruff` is unavailable, run the existing approved equivalent:

```powershell
uvx ruff check service sdk tests
```

and report the mismatch so the repo can standardize later.

- [ ] **Step 4: Update README configuration docs**

Add a short README environment entry for the workflow settings:

```markdown
| `ENABLE_AGENT_WORKFLOW_MODE` | `false` | Enables opt-in agent workflow mode for `/api/chat`. |
| `AGENT_WORKFLOW_TIMEOUT_SECONDS` | `20.0` | Timeout for workflow-mode chat requests. |
| `AGENT_WORKFLOW_MAX_ROUNDS` | `2` | Maximum LLM/tool rounds for workflow-mode requests. |
```

- [ ] **Step 5: Mark final OpenSpec tasks complete**

Update `tasks.md`:

```markdown
- [x] 6.3 Run the targeted agent, tool, and chat test suites.
- [x] 6.4 Run OpenSpec validation for `agent-workflow-foundation`.
- [x] 6.5 Update README or developer docs if the new mode setting or workflow tools need local usage guidance.
```

- [ ] **Step 6: Final status and commit**

Run:

```powershell
git status --short
git diff --stat
```

Ensure only intended files are changed. Commit:

```powershell
git add -- README.md openspec\changes\agent-workflow-foundation\tasks.md
git commit -m "docs: document agent workflow mode"
```

If README did not need changes, commit only `tasks.md`:

```powershell
git add -- openspec\changes\agent-workflow-foundation\tasks.md
git commit -m "docs: complete agent workflow openspec tasks"
```

## Self-Review

- Spec coverage: all OpenSpec tasks 1.1 through 6.5 map to at least one implementation plan task.
- Placeholder scan: no placeholders, TBDs, or open implementation choices remain.
- Type consistency: `agent_mode`, `legacy`, `workflow`, `collect_market_context`, `analyze_market_context`, and `generate_market_briefing` are used consistently across tasks.
- Compatibility: `/api/chat` response fields remain `reply`, `data`, and `tool_used`.
- Safety: workflow mode stays disabled by default and does not silently fall back to legacy mode.
