# Sub-Agent Architecture Flow

## Overview
AI Market Studio uses a **multi-agent orchestration pattern** where GPT-4o acts as the orchestrator coordinating 4 specialized sub-agents.

## Complete Flow: UI Query → Sub-Agent Operation

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. USER QUERY (Frontend)                                            │
│    "Give me a market insight on EUR/USD and GBP/USD"                │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. HTTP REQUEST                                                      │
│    POST /api/chat                                                    │
│    Body: { message: "...", history: [...] }                         │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. BACKEND ROUTER (router.py)                                       │
│    - Receives request                                                │
│    - Creates connectors (market, news, FRED, RAG)                   │
│    - Calls run_agent()                                               │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. ORCHESTRATOR (agent.py - run_agent)                              │
│    - Builds conversation context with SYSTEM_PROMPT                 │
│    - Sends to GPT-4o with TOOL_DEFINITIONS                          │
│    - Enters tool-calling loop (max 3 rounds)                        │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. GPT-4o DECISION (OpenAI API)                                     │
│    Analyzes: "market insight on EUR/USD and GBP/USD"                │
│    Decides: Need to collect data then synthesize                    │
│                                                                      │
│    ROUND 1: Parallel data collection                                │
│    ├─ Tool Call 1: collect_market_data(                             │
│    │    data_type="rates", pairs=["EUR/USD", "GBP/USD"])            │
│    └─ Tool Call 2: collect_market_data(                             │
│         data_type="news", query="EUR USD GBP")                      │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 6. TOOL DISPATCH (tools.py - dispatch_tool)                         │
│    For each tool call:                                               │
│    ├─ collect_market_data → data_collector.py                       │
│    │   ├─ Routes by data_type                                       │
│    │   ├─ Calls appropriate connector                               │
│    │   └─ Returns: {data_type, source, data, metadata}              │
│    │                                                                 │
│    └─ Returns results to orchestrator                               │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 7. ORCHESTRATOR LOOP CONTINUES                                      │
│    - Appends tool results to conversation                           │
│    - Sends back to GPT-4o                                            │
│                                                                      │
│    ROUND 2: Synthesis                                               │
│    GPT-4o sees collected data and calls:                            │
│    Tool Call: synthesize_research(                                  │
│      sources={                                                       │
│        "rates": <full rates_result>,                                │
│        "news": <full news_result>                                   │
│      }                                                               │
│    )                                                                 │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 8. SUB-AGENT EXECUTION (research_synthesizer.py)                    │
│    synthesize_research():                                           │
│    ├─ Analyzes rates data → extract insights                        │
│    ├─ Analyzes news data → extract insights                         │
│    ├─ Generates synthesis narrative                                 │
│    ├─ Calculates confidence score                                   │
│    └─ Returns: {synthesis, key_insights, sources_used, confidence}  │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 9. ORCHESTRATOR FINAL RESPONSE                                      │
│    - GPT-4o receives synthesis result                               │
│    - Generates natural language response                            │
│    - finish_reason = "stop" (no more tool calls)                    │
│    - Returns: {reply, data, tool_used}                              │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 10. RESPONSE TO USER                                                │
│     Frontend receives:                                               │
│     - reply: "Based on current data, EUR/USD is at 1.0868..."       │
│     - data: {synthesis, key_insights, ...}                          │
│     - Renders in chat UI                                             │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Orchestrator (agent.py)
- **Role**: Coordinates all sub-agents
- **Responsibilities**:
  - Maintains conversation context
  - Sends requests to GPT-4o with tool definitions
  - Executes tool calls via dispatch_tool()
  - Manages tool-calling loop (max 3 rounds)

### 2. GPT-4o (OpenAI API)
- **Role**: Decision maker
- **Responsibilities**:
  - Understands user intent
  - Decides which tools to call and in what order
  - Determines parallel vs sequential execution
  - Generates final natural language response

### 3. Tool Dispatcher (tools.py)
- **Role**: Routes tool calls to sub-agents
- **Responsibilities**:
  - Validates tool names
  - Extracts tool arguments
  - Calls appropriate sub-agent function
  - Returns results to orchestrator

### 4. Sub-Agents (agents/*.py)

#### Data Collector (data_collector.py)
- **Purpose**: Fetch raw market data
- **Operations**:
  - `data_type="rates"` → MarketDataConnector
  - `data_type="news"` → NewsConnector
  - `data_type="fred"` → FREDConnector
  - `data_type="rag"` → RAGConnector
- **Output**: `{data_type, source, data, metadata}`

#### Market Analyst (market_analyst.py)
- **Purpose**: Analyze trends, volatility, correlations
- **Operations**:
  - `analysis_type="trend"` → trend analysis
  - `analysis_type="volatility"` → volatility metrics
  - `analysis_type="correlation"` → correlation matrix
  - `analysis_type="signal"` → trading signals
- **Output**: `{analysis_type, results, confidence}`

#### Research Synthesizer (research_synthesizer.py)
- **Purpose**: Combine multi-source intelligence
- **Operations**:
  - Analyzes rates data → extract rate insights
  - Analyzes news data → count articles
  - Analyzes FRED data → economic indicators
  - Analyzes RAG data → research findings
  - Generates coherent narrative
- **Output**: `{synthesis, key_insights, sources_used, confidence}`

#### Report Generator (report_generator.py)
- **Purpose**: Create formatted outputs
- **Operations**:
  - `format="pdf"` → PDF export
  - `format="dashboard"` → visual dashboard
  - `format="summary"` → text summary
- **Output**: `{format, content, metadata}`

## Execution Patterns

### Parallel Execution
When data sources are independent:
```python
# GPT-4o calls these in the SAME round
collect_market_data(data_type="rates", pairs=["EUR/USD"])
collect_market_data(data_type="news", query="EUR USD")
collect_market_data(data_type="fred", series_id="DFF")
```

### Sequential Execution
When one agent depends on another:
```python
# Round 1: Collect data (parallel)
rates_result = collect_market_data(data_type="rates", ...)
news_result = collect_market_data(data_type="news", ...)

# Round 2: Synthesize (depends on Round 1)
synthesis = synthesize_research(sources={
    "rates": rates_result,
    "news": news_result
})

# Round 3: Generate response
# GPT-4o creates natural language response
```

## Data Flow Example

**Query**: "Give me a market insight on EUR/USD and GBP/USD"

**Round 1 - Data Collection**:
```json
// Tool Call 1
collect_market_data(data_type="rates", pairs=["EUR/USD", "GBP/USD"])
→ Returns: {
    "data_type": "rates",
    "source": "exchangerate.host",
    "data": [
      {"base": "EUR", "target": "USD", "rate": 1.0868, "date": "2026-04-28"},
      {"base": "GBP", "target": "USD", "rate": 1.2729, "date": "2026-04-28"}
    ],
    "metadata": {"count": 2, "timestamp": "..."}
  }

// Tool Call 2
collect_market_data(data_type="news", query="EUR USD GBP")
→ Returns: {
    "data_type": "news",
    "source": "RSS",
    "data": [
      {"title": "EUR strengthens...", "url": "...", "published": "..."}
    ],
    "metadata": {"count": 1, "query": "EUR USD GBP"}
  }
```

**Round 2 - Synthesis**:
```json
// Tool Call
synthesize_research(sources={
  "rates": <full rates_result from Round 1>,
  "news": <full news_result from Round 1>
})
→ Returns: {
    "synthesis": "Exchange rate up +17.12% to 1.2729. News coverage: 1 recent articles",
    "key_insights": [
      "Exchange rate up +17.12% to 1.2729",
      "News coverage: 1 recent articles"
    ],
    "sources_used": [
      {"type": "rates", "count": 2},
      {"type": "news", "count": 1}
    ],
    "confidence": 0.29
  }
```

**Round 3 - Final Response**:
```
GPT-4o generates natural language:
"Based on current market data, EUR/USD is trading at 1.0868 and GBP/USD at 1.2729.
The GBP has shown significant strength with a 17% increase. There is limited news
coverage at the moment with 1 recent article."
```

## Configuration

### System Prompt (agent.py)
Instructs GPT-4o on:
- Available sub-agents and their purposes
- When to use each sub-agent
- Parallel vs sequential execution patterns
- Data format requirements

### Tool Definitions (tools.py)
Defines for GPT-4o:
- Tool names and descriptions
- Required/optional parameters
- Parameter types and formats
- Usage examples

### Connectors
Provide data access:
- MarketDataConnector → FX rates
- NewsConnector → Market news
- FREDConnector → Economic indicators
- RAGConnector → Research documents

## Error Handling

1. **Connector Errors**: Caught and returned as `{"error": "..."}` to GPT-4o
2. **Agent Errors**: Logged and returned as `{"error": "..."}` to GPT-4o
3. **Max Rounds**: If 3 rounds exhausted, returns fallback message
4. **Tool Validation**: Unknown tools raise AgentError

## Observability

Tracked metrics:
- LLM calls (provider, model)
- Token usage (prompt + completion)
- Tool calls (name, args, duration)
- Errors and exceptions
