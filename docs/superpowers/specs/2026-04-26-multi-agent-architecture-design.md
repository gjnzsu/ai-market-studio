# AI Market Studio - Multi-Agent Architecture Design

> **Date:** 2026-04-26  
> **Status:** Draft - Awaiting Approval  
> **Author:** Claude (Brainstorming Session)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Frontend UI Changes](#3-frontend-ui-changes)
4. [Sub-Agent Specifications](#4-sub-agent-specifications)
5. [Orchestrator Changes](#5-orchestrator-changes)
6. [Implementation Details](#6-implementation-details)
7. [Success Metrics & Next Steps](#7-success-metrics--next-steps)

---

## 1. Executive Summary

### Vision

Transform AI Market Studio from a single-agent chatbot into a **multi-agent orchestration system** where specialized sub-agents collaborate to deliver comprehensive FX market intelligence.

### Architecture Pattern

**Hybrid (Hierarchical + Parallel)** - An orchestrator manages specialized sub-agents and executes them in parallel when tasks are independent.

### Agent Team

- **Orchestrator**: Conversational Agent (GPT-4o/5.x) - coordinates all sub-agents
- **Sub-Agent 1**: Data Collector - fetches raw market data
- **Sub-Agent 2**: Market Analyst - analyzes trends and patterns
- **Sub-Agent 3**: Report Generator - creates formatted outputs
- **Sub-Agent 4**: Research Synthesizer - combines multi-source intelligence

### Implementation Approach

**Sub-Agents as Function Tools** - Each sub-agent is implemented as a Python function that GPT-4o/5.x calls via function calling. This leverages existing architecture and minimizes refactoring.

### Key Benefits

1. **Clear separation of concerns** - Each agent has focused responsibility
2. **Parallel execution** - Independent data collection runs concurrently
3. **Easier testing** - Sub-agents can be tested independently
4. **Scalability** - Can evolve sub-agents to independent LLM agents later
5. **User transparency** - Agent activity panel shows workflow progress

---

## 2. System Architecture

### Current State (Before)

```
User → Frontend → Backend API → GPT-4o Agent → Individual Tools
                                      ↓
                        (get_exchange_rate, get_fx_news, 
                         get_interest_rate, generate_dashboard, etc.)
                                      ↓
                                  Connectors
```

**Current Tools (8 total):**
- `get_exchange_rate` - Single pair spot rate
- `get_exchange_rates` - Multiple pairs spot rates
- `get_historical_rates` - Historical rate series
- `get_interest_rate` - FRED economic indicators
- `generate_dashboard` - Inline Chart.js visualization
- `get_fx_news` - RSS news feeds
- `generate_market_insight` - Combined rates + news
- `get_internal_research` - RAG document queries

### Target State (After)

```
User → Frontend → Backend API → Orchestrator (GPT-4o/5.x)
                                      ↓
                        Sub-Agent Function Tools (4 agents)
                                      ↓
                    ┌─────────────────┼─────────────────┐
                    ↓                 ↓                 ↓
            Data Collector    Market Analyst    Report Generator
                    ↓                                   ↓
            (all connectors)              Research Synthesizer
```

**New Sub-Agent Tools (4 total):**
- `collect_market_data` - Unified data fetching (rates, news, FRED, RAG)
- `analyze_market_trends` - Statistical analysis and trend detection
- `generate_report` - Formatted outputs (PDF, dashboard, summary)
- `synthesize_research` - Multi-source intelligence synthesis

### Key Changes

1. **Consolidate 8 tools into 4 sub-agents** - Clearer boundaries, easier to maintain
2. **Orchestrator remains GPT-4o/5.x** - Minimal changes to agent.py
3. **Sub-agents are Python functions** - Implemented in `backend/agents/` directory
4. **Parallel execution** - Handled automatically by GPT function calling
5. **Agent activity visibility** - New UI panel shows real-time agent status

### File Structure

```
backend/
├── agent/
│   ├── agent.py              # Orchestrator (existing, minor updates)
│   └── tools.py              # Tool definitions (refactored)
├── agents/                   # NEW: Sub-agent implementations
│   ├── __init__.py
│   ├── data_collector.py     # Data Collector agent
│   ├── market_analyst.py     # Market Analyst agent
│   ├── report_generator.py   # Report Generator agent
│   └── research_synthesizer.py  # Research Synthesizer agent
├── connectors/               # Existing (unchanged)
│   ├── base.py
│   ├── exchangerate_host.py
│   ├── fred_connector.py
│   ├── news_connector.py
│   └── rag_connector.py
└── models.py                 # Add new sub-agent request/response models
```

---

## 3. Frontend UI Changes

### Current UI State

- Single chat interface
- Inline responses (charts, news cards, rate chips)
- Export to PDF button
- Pre-defined query chips

### Proposed UI Enhancement: Agent Activity Panel

```
┌─────────────────────────────────────────────────────┐
│  AI Market Studio                                    │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Chat Messages                    │  Agent Activity │
│  ┌──────────────────────────┐    │  ┌─────────────┐│
│  │ User: Analyze EUR/USD    │    │  │ 🔵 Data     ││
│  │                          │    │  │    Collector││
│  │ Assistant: [analyzing]   │    │  │             ││
│  │                          │    │  │ 🟢 Market   ││
│  │                          │    │  │    Analyst  ││
│  │                          │    │  │             ││
│  │                          │    │  │ ⚪ Report   ││
│  │                          │    │  │    Generator││
│  └──────────────────────────┘    │  └─────────────┘│
│                                   │                  │
└───────────────────────────────────────────────────────┘
```

### Features

- **Right sidebar** shows which agents are active
- **Status indicators**:
  - 🔵 Working (agent currently executing)
  - 🟢 Complete (agent finished successfully)
  - ⚪ Idle (agent not involved in current request)
  - 🔴 Error (agent encountered an error)
- **Real-time updates** as orchestrator calls sub-agents
- **Collapsible sidebar** (can hide for more chat space)
- **Click agent** to see detailed logs (optional, future enhancement)

### Implementation Notes

- **WebSocket or polling** for real-time agent status updates
- **Backend sends agent events** when sub-agents are called
- **Frontend updates UI** based on events
- **Graceful degradation** if WebSocket unavailable (no sidebar)

### UI Repository

Frontend changes will be in the separate `ai-market-studio-ui` repository.

---

## 4. Sub-Agent Specifications

### 4.1 Data Collector Agent

**Purpose:** Fetch raw market data from all sources (FX rates, news, FRED, research documents)

**Function Signature:**
```python
async def collect_market_data(
    data_type: Literal["rates", "news", "fred", "rag"],
    pairs: Optional[List[str]] = None,
    days: Optional[int] = None,
    series_id: Optional[str] = None,
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]
```

**Responsibilities:**
- Route to appropriate connector based on `data_type`
- Handle errors and retries
- Return normalized data structure
- Support parallel execution (multiple calls in same round)

**Tool Definition (GPT function):**
```json
{
  "name": "collect_market_data",
  "description": "Fetch market data from various sources (FX rates, news, FRED economic indicators, research documents)",
  "parameters": {
    "type": "object",
    "properties": {
      "data_type": {
        "type": "string",
        "enum": ["rates", "news", "fred", "rag"],
        "description": "Type of data to collect"
      },
      "pairs": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Currency pairs (e.g., ['EUR/USD', 'GBP/USD'])"
      },
      "days": {
        "type": "integer",
        "description": "Number of days of historical data"
      },
      "series_id": {
        "type": "string",
        "description": "FRED series ID (e.g., 'DFF', 'DGS10')"
      },
      "query": {
        "type": "string",
        "description": "Search query for news or RAG"
      }
    },
    "required": ["data_type"]
  }
}
```

**Output Format:**
```python
{
  "data_type": "rates",
  "source": "exchangerate.host",
  "data": [...],  # Connector-specific format
  "metadata": {
    "fetched_at": "2026-04-26T10:00:00Z",
    "cache_hit": false,
    "quota_used": 1
  }
}
```

**Connector Mapping:**
- `data_type="rates"` → ExchangeRateHostConnector or MockConnector
- `data_type="news"` → RSSNewsConnector or MockNewsConnector
- `data_type="fred"` → FREDConnector
- `data_type="rag"` → RAGConnector

### 4.2 Market Analyst Agent

**Purpose:** Analyze FX market data for trends, volatility, correlations, and trading signals

**Function Signature:**
```python
async def analyze_market_trends(
    data: Dict[str, Any],
    analysis_type: Literal["trend", "volatility", "correlation", "signal"] = "trend",
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```

**Responsibilities:**
- Compute statistical indicators (moving averages, volatility, momentum)
- Detect trends (uptrend, downtrend, sideways)
- Generate trading signals (buy, sell, hold)
- Correlate with economic indicators if context provided

**Tool Definition (GPT function):**
```json
{
  "name": "analyze_market_trends",
  "description": "Analyze FX market data for trends, volatility, correlations, and trading signals",
  "parameters": {
    "type": "object",
    "properties": {
      "data": {
        "type": "object",
        "description": "Market data from Data Collector"
      },
      "analysis_type": {
        "type": "string",
        "enum": ["trend", "volatility", "correlation", "signal"],
        "description": "Type of analysis to perform"
      },
      "context": {
        "type": "object",
        "description": "Additional context (news, economic indicators)"
      }
    },
    "required": ["data"]
  }
}
```

**Output Format:**
```python
{
  "analysis_type": "trend",
  "pair": "EUR/USD",
  "trend_direction": "uptrend",
  "strength": 0.75,  # 0-1 scale
  "indicators": {
    "sma_20": 1.0850,
    "volatility": 0.0045,
    "momentum": 0.32
  },
  "signals": ["buy"],
  "confidence": 0.68,
  "summary": "EUR/USD shows strong upward momentum with increasing volatility..."
}
```

**Analysis Types:**
- `trend` - Direction, strength, support/resistance levels
- `volatility` - Historical volatility, volatility spikes
- `correlation` - Correlation with other pairs or economic indicators
- `signal` - Trading signals based on technical indicators

### 4.3 Report Generator Agent

**Purpose:** Create formatted outputs (PDFs, dashboards, summaries) from market data and analysis

**Function Signature:**
```python
async def generate_report(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]] = None,
    format: Literal["pdf", "dashboard", "summary"] = "summary",
    title: Optional[str] = None
) -> Dict[str, Any]
```

**Responsibilities:**
- Generate PDF reports using existing PDF skill
- Create inline Chart.js dashboards
- Format text summaries
- Combine multiple data sources into cohesive output

**Tool Definition (GPT function):**
```json
{
  "name": "generate_report",
  "description": "Generate formatted reports, dashboards, or summaries from market data and analysis",
  "parameters": {
    "type": "object",
    "properties": {
      "data": {
        "type": "object",
        "description": "Market data to include in report"
      },
      "analysis": {
        "type": "object",
        "description": "Analysis results to include"
      },
      "format": {
        "type": "string",
        "enum": ["pdf", "dashboard", "summary"],
        "description": "Output format"
      },
      "title": {
        "type": "string",
        "description": "Report title"
      }
    },
    "required": ["data", "format"]
  }
}
```

**Output Format:**
```python
{
  "format": "pdf",
  "title": "EUR/USD Market Analysis Report",
  "content": {
    "pdf_url": "/api/export/pdf?id=abc123",
    "filename": "fx-analysis-20260426.pdf",
    "size_bytes": 45678
  },
  "metadata": {
    "generated_at": "2026-04-26T10:00:00Z",
    "pages": 3
  }
}
```

**Format Types:**
- `pdf` - Downloadable PDF report (uses existing PDF skill)
- `dashboard` - Inline Chart.js visualization
- `summary` - Text summary for chat response

### 4.4 Research Synthesizer Agent

**Purpose:** Combine multi-source market intelligence (rates, news, economic data, research) into coherent insights

**Function Signature:**
```python
async def synthesize_research(
    sources: Dict[str, Any],  # {rates: ..., news: ..., rag: ..., fred: ...}
    focus: Optional[str] = None,  # What aspect to emphasize
    max_sources: int = 10
) -> Dict[str, Any]
```

**Responsibilities:**
- Combine data from multiple sources (rates, news, FRED, RAG)
- Identify correlations and connections
- Generate coherent narrative synthesis
- Prioritize most relevant information

**Tool Definition (GPT function):**
```json
{
  "name": "synthesize_research",
  "description": "Combine multi-source market intelligence (rates, news, economic data, research) into coherent insights",
  "parameters": {
    "type": "object",
    "properties": {
      "sources": {
        "type": "object",
        "description": "Data from multiple sources (rates, news, fred, rag)"
      },
      "focus": {
        "type": "string",
        "description": "Aspect to emphasize (e.g., 'interest rates', 'technical analysis')"
      },
      "max_sources": {
        "type": "integer",
        "description": "Maximum number of sources to include"
      }
    },
    "required": ["sources"]
  }
}
```

**Output Format:**
```python
{
  "synthesis": "EUR/USD shows upward momentum (+0.65% over 30 days) correlating with ECB rate hold signals and dovish Fed pivot...",
  "key_insights": [
    "Interest rate differential narrowing favors EUR",
    "Technical indicators confirm uptrend",
    "News sentiment: 70% positive for EUR"
  ],
  "sources_used": [
    {"type": "rates", "count": 30},
    {"type": "news", "count": 5},
    {"type": "fred", "series": ["DFF", "T10Y2Y"]},
    {"type": "rag", "documents": 2}
  ],
  "confidence": 0.82
}
```

**Synthesis Logic:**
- Identify correlations between rate movements and news/economic events
- Weight sources by relevance and recency
- Generate narrative that connects the dots
- Provide confidence score based on source agreement

---

## 5. Orchestrator Changes

### Current Orchestrator (agent.py)

- GPT-4o with 8 individual function tools
- Each tool maps to a specific connector or feature
- Tools: `get_exchange_rate`, `get_exchange_rates`, `get_historical_rates`, `get_interest_rate`, `generate_dashboard`, `get_fx_news`, `generate_market_insight`, `get_internal_research`

### Updated Orchestrator (agent.py)

**Minimal Changes Required:**

1. **Update TOOL_DEFINITIONS** in `backend/agent/tools.py`
   - Replace 8 existing tools with 4 sub-agent tools
   - Keep tool definition structure (GPT function calling format)

2. **Update dispatch_tool()** in `backend/agent/tools.py`
   - Route to new sub-agent functions instead of direct connector calls
   - Pass connectors as dependencies to sub-agents

3. **Update SYSTEM_PROMPT** in `backend/agent/agent.py`
   - Describe the 4 sub-agents and their capabilities
   - Guide orchestrator on when to use each agent
   - Emphasize parallel execution for independent data collection

**New System Prompt (excerpt):**
```python
SYSTEM_PROMPT = """
You are the orchestrator for AI Market Studio, a multi-agent FX market intelligence platform.

You coordinate 4 specialized sub-agents:

1. **Data Collector** - Fetches raw market data (FX rates, news, FRED, research)
   - Use when you need to retrieve any market data
   - Can be called multiple times in parallel for different data types

2. **Market Analyst** - Analyzes trends, volatility, correlations, signals
   - Use after collecting data to perform technical/statistical analysis
   - Requires data from Data Collector as input

3. **Report Generator** - Creates PDFs, dashboards, summaries
   - Use when user requests formatted output
   - Can work with raw data or analysis results

4. **Research Synthesizer** - Combines multi-source intelligence
   - Use when user asks for comprehensive insights across sources
   - Requires data from multiple sources (rates + news + FRED + RAG)

**Parallel Execution:**
When fetching data from multiple independent sources, call Data Collector multiple times in parallel.
Example: For "market insight on EUR/USD", call:
- collect_market_data(data_type="rates", pairs=["EUR/USD"])
- collect_market_data(data_type="news", query="EUR USD")
- collect_market_data(data_type="fred", series_id="DFF")
All in the same function calling round.

**Sequential Execution:**
When one agent depends on another's output, call them sequentially.
Example: For "analyze EUR/USD trend", call:
1. collect_market_data(data_type="rates", pairs=["EUR/USD"], days=30)
2. analyze_market_trends(data=<result_from_step_1>)
"""
```

**Agent Loop (agent.py) - No Changes Needed:**
- Existing `run_agent()` function already handles parallel/sequential tool calls
- GPT-4o/5.x automatically decides when to parallelize
- No refactoring required for the main agent loop

---

## 6. Implementation Details

### Migration Strategy

**Phase 1: Create Sub-Agent Structure (No Breaking Changes)**
1. Create `backend/agents/` directory with 4 sub-agent modules
2. Implement sub-agent functions that wrap existing logic
3. Keep existing tools working (backward compatibility)
4. Add new sub-agent tool definitions alongside old tools

**Phase 2: Update Orchestrator**
1. Add 4 new sub-agent tools to TOOL_DEFINITIONS
2. Update SYSTEM_PROMPT to describe sub-agents
3. Test with both old and new tools active
4. Verify parallel execution works

**Phase 3: Deprecate Old Tools**
1. Remove old tool definitions from TOOL_DEFINITIONS
2. Remove old dispatch handlers
3. Update frontend to show agent activity panel
4. Deploy to GKE

### Code Mapping: Old Tools → New Sub-Agents

**Data Collector Agent** consolidates:
- `get_exchange_rate` → `collect_market_data(data_type="rates", pairs=[...])`
- `get_exchange_rates` → `collect_market_data(data_type="rates", pairs=[...])`
- `get_historical_rates` → `collect_market_data(data_type="rates", days=...)`
- `get_interest_rate` → `collect_market_data(data_type="fred", series_id=...)`
- `get_fx_news` → `collect_market_data(data_type="news", query=...)`
- `get_internal_research` → `collect_market_data(data_type="rag", query=...)`

**Market Analyst Agent** is NEW:
- Extracts analysis logic from `generate_market_insight`
- Adds statistical analysis capabilities
- Computes trends, volatility, correlations

**Report Generator Agent** consolidates:
- `generate_dashboard` → `generate_report(format="dashboard")`
- PDF export logic → `generate_report(format="pdf")`

**Research Synthesizer Agent** consolidates:
- `generate_market_insight` → `synthesize_research(sources={...})`
- Combines rates + news + FRED + RAG

### New Files to Create

```
backend/agents/__init__.py
backend/agents/data_collector.py      # ~150 lines
backend/agents/market_analyst.py      # ~200 lines (new analysis logic)
backend/agents/report_generator.py    # ~100 lines
backend/agents/research_synthesizer.py # ~150 lines
```

### Modified Files

```
backend/agent/tools.py                # Replace tool definitions, update dispatch
backend/agent/agent.py                # Update SYSTEM_PROMPT
backend/models.py                     # Add sub-agent request/response models
```

### Frontend Changes

```
frontend/index.html (ai-market-studio-ui repo)
- Add agent activity panel (right sidebar)
- Add WebSocket or polling for real-time agent status
- Update CSS for new layout
```

### Testing Strategy

1. **Unit Tests** - Test each sub-agent function independently
   - Mock connector responses
   - Test error handling
   - Verify output format

2. **Integration Tests** - Test orchestrator → sub-agent flow
   - Test parallel execution
   - Test sequential execution
   - Test error propagation

3. **E2E Tests** - Test full user workflows with new architecture
   - Simple query (single agent)
   - Multi-step workflow (sequential agents)
   - Parallel workflow (multiple agents)
   - Complex workflow (parallel + sequential)

4. **Backward Compatibility Tests** - Ensure existing queries still work during migration
   - Run existing test suite with new architecture
   - Verify response formats unchanged
   - Check performance benchmarks

### Deployment Considerations

- **Zero Downtime**: Phase 1 & 2 don't break existing functionality
- **Rollback Plan**: Keep old tools active until Phase 3 is verified
- **Observability**: AI SRE Observability tracks sub-agent calls separately
- **Cost Impact**: Same number of LLM calls (tools → sub-agents 1:1 mapping)
- **Model Upgrade**: Architecture works seamlessly with GPT-5.x

### Example Workflows

**Simple Query: "What is EUR/USD today?"**
1. User sends message
2. Orchestrator (GPT-4o) detects intent: spot rate query
3. Calls `collect_market_data(data_type="rates", pairs=["EUR/USD"])`
4. Data Collector fetches from ExchangeRateHostConnector
5. Returns rate to orchestrator
6. Orchestrator composes natural language response

**Multi-Step: "Analyze EUR/USD trend and create a PDF report"**
1. User sends message
2. Orchestrator detects intent: trend analysis + report
3. Calls `collect_market_data(data_type="rates", pairs=["EUR/USD"], days=30)`
4. Data Collector fetches historical rates
5. Calls `analyze_market_trends(data=rates)`
6. Market Analyst computes trends, volatility, signals
7. Calls `generate_report(analysis=results, format="pdf")`
8. Report Generator creates PDF
9. Returns PDF download link

**Parallel: "Give me market insight on EUR/USD, GBP/USD, and USD/JPY"**
1. User sends message
2. Orchestrator detects intent: multi-pair market insight
3. **Parallel calls:**
   - `collect_market_data(data_type="rates", pairs=["EUR/USD","GBP/USD","USD/JPY"])`
   - `collect_market_data(data_type="news", query="FX")`
   - `collect_market_data(data_type="fred", series_id="DFF")`
4. Calls `synthesize_research(sources={rates, news, fred})`
5. Research Synthesizer combines all sources
6. Returns inline insight with rate chips + news cards

---

## 7. Success Metrics & Next Steps

### Success Metrics

**Technical Metrics:**
- **Parallel Execution Rate**: % of requests that trigger parallel sub-agent calls (target: >40%)
- **Response Latency**: P95 latency for multi-agent workflows (target: <5s)
- **Agent Utilization**: Which sub-agents are called most frequently
- **Error Rate**: Sub-agent failures per 1000 requests (target: <1%)

**User Experience Metrics:**
- **Agent Visibility**: % of users who interact with agent activity panel
- **Query Complexity**: Average number of sub-agents per user request
- **User Satisfaction**: Feedback on multi-agent transparency

**Cost Metrics:**
- **LLM Cost per Request**: Should remain similar to current (1 orchestrator call + N tool calls)
- **Token Usage**: Track prompt/completion tokens per sub-agent
- **Cost by Agent**: Which sub-agents consume most tokens

### Observability Integration

Leverage existing AI SRE Observability to track:
```python
# Each sub-agent call tracked separately
llm_requests_total{agent="data_collector"}
llm_requests_total{agent="market_analyst"}
llm_requests_total{agent="report_generator"}
llm_requests_total{agent="research_synthesizer"}

# New metrics
agent_calls_total{agent="...", status="success|error"}
agent_latency_seconds{agent="..."}
agent_parallel_execution_total
```

### Future Enhancements (Post-MVP)

**Phase 2: Hybrid Implementation**
- Convert Market Analyst to independent LLM agent (needs reasoning)
- Convert Research Synthesizer to independent LLM agent (needs reasoning)
- Keep Data Collector and Report Generator as tools (deterministic)

**Phase 3: Advanced Features**
- **Risk Monitor Agent**: Real-time anomaly detection and alerts
- **Strategy Backtester Agent**: Test trading strategies on historical data
- **Portfolio Optimizer Agent**: Multi-currency portfolio optimization

**Phase 4: Autonomous Workflows**
- Scheduled reports (daily market summary)
- Proactive alerts (threshold breaches)
- Continuous monitoring mode

### Implementation Timeline

**Phase 1: Sub-Agent Structure** (2-3 days)
- Create `backend/agents/` directory
- Implement 4 sub-agent functions
- Add unit tests
- Verify backward compatibility

**Phase 2: Orchestrator Update** (1-2 days)
- Update tool definitions and system prompt
- Add agent activity panel to frontend
- Integration testing
- Verify parallel execution

**Phase 3: Deployment** (1 day)
- Deploy to GKE
- Monitor metrics
- Deprecate old tools
- Update documentation

**Total Estimated Time:** 4-6 days

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing queries | HIGH | Phase 1 & 2 maintain backward compatibility |
| Increased latency | MEDIUM | Parallel execution offsets sequential overhead |
| Frontend complexity | MEDIUM | Agent panel is optional, graceful degradation |
| Cost increase | LOW | Same number of LLM calls, no cost change |
| GPT-5.x compatibility | LOW | Architecture is model-agnostic |

### Approval Checklist

- [ ] Architecture pattern approved (Hybrid Hierarchical + Parallel)
- [ ] Sub-agent responsibilities clear and non-overlapping
- [ ] UI changes acceptable (Agent Activity Panel)
- [ ] Implementation approach feasible (Function Tools)
- [ ] Migration strategy safe (3-phase rollout)
- [ ] Timeline realistic (4-6 days)

---

**End of Design Document**