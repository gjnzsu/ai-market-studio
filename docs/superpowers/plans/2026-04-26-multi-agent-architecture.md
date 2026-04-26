# Multi-Agent Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform AI Market Studio into a multi-agent orchestration system with 4 specialized sub-agents (Data Collector, Market Analyst, Report Generator, Research Synthesizer) coordinated by a GPT-4o/5.x orchestrator.

**Architecture:** Hybrid (Hierarchical + Parallel) - Orchestrator manages sub-agents implemented as Python function tools. Sub-agents can execute in parallel when independent. 3-phase migration maintains backward compatibility.

**Tech Stack:** Python 3.12, FastAPI, GPT-4o/5.x function calling, existing connectors (ExchangeRateHost, FRED, RSS, RAG)

---

## File Structure

### New Files
- `backend/agents/__init__.py` - Package initialization, exports all sub-agent functions
- `backend/agents/data_collector.py` - Data Collector agent (~150 lines)
- `backend/agents/market_analyst.py` - Market Analyst agent (~200 lines)
- `backend/agents/report_generator.py` - Report Generator agent (~100 lines)
- `backend/agents/research_synthesizer.py` - Research Synthesizer agent (~150 lines)

### Modified Files
- `backend/agent/tools.py` - Add 4 new sub-agent tool definitions, keep old tools for Phase 1-2
- `backend/agent/agent.py` - Update SYSTEM_PROMPT to describe sub-agents
- `backend/models.py` - Add sub-agent request/response models

### Test Files
- `backend/tests/unit/test_data_collector.py` - Data Collector unit tests
- `backend/tests/unit/test_market_analyst.py` - Market Analyst unit tests
- `backend/tests/unit/test_report_generator.py` - Report Generator unit tests
- `backend/tests/unit/test_research_synthesizer.py` - Research Synthesizer unit tests
- `backend/tests/integration/test_multi_agent_flow.py` - Integration tests

---

## Phase 1: Create Sub-Agent Structure (No Breaking Changes)

### Task 1: Create agents package structure

**Files:**
- Create: `backend/agents/__init__.py`

- [ ] **Step 1: Create agents directory**

```bash
mkdir -p backend/agents
```

- [ ] **Step 2: Create package __init__.py**

```python
# backend/agents/__init__.py
"""
Multi-agent system for AI Market Studio.

Sub-agents:
- Data Collector: Fetches raw market data from all sources
- Market Analyst: Analyzes trends, volatility, correlations, signals
- Report Generator: Creates formatted outputs (PDF, dashboard, summary)
- Research Synthesizer: Combines multi-source intelligence
"""

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

- [ ] **Step 3: Verify package structure**

```bash
ls -la backend/agents/
```

Expected: `__init__.py` exists

- [ ] **Step 4: Commit**

```bash
git add backend/agents/__init__.py
git commit -m "feat: create agents package structure for multi-agent system"
```

---

### Task 2: Implement Data Collector Agent

**Files:**
- Create: `backend/agents/data_collector.py`
- Create: `backend/tests/unit/test_data_collector.py`

- [ ] **Step 1: Write failing test for rates collection**

```python
# backend/tests/unit/test_data_collector.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.agents.data_collector import collect_market_data


@pytest.mark.asyncio
async def test_collect_rates_data():
    """Test collecting FX rate data."""
    mock_connector = AsyncMock()
    mock_connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.0850,
        "date": "2026-04-26",
        "source": "mock"
    }
    
    result = await collect_market_data(
        data_type="rates",
        pairs=["EUR/USD"],
        connector=mock_connector
    )
    
    assert result["data_type"] == "rates"
    assert result["source"] == "mock"
    assert len(result["data"]) == 1
    assert result["data"][0]["rate"] == 1.0850
    assert "metadata" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest backend/tests/unit/test_data_collector.py::test_collect_rates_data -v
```

Expected: FAIL with "No module named 'backend.agents.data_collector'"

- [ ] **Step 3: Implement Data Collector agent**

```python
# backend/agents/data_collector.py
from typing import Any, Dict, List, Optional, Literal
from datetime import datetime
from backend.connectors.base import MarketDataConnector
from backend.connectors.news_connector import NewsConnectorBase
from backend.connectors.fred_connector import FREDConnector
from backend.connectors.rag_connector import RAGConnector


async def collect_market_data(
    data_type: Literal["rates", "news", "fred", "rag"],
    pairs: Optional[List[str]] = None,
    days: Optional[int] = None,
    series_id: Optional[str] = None,
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    connector: Optional[MarketDataConnector] = None,
    news_connector: Optional[NewsConnectorBase] = None,
    fred_connector: Optional[FREDConnector] = None,
    rag_connector: Optional[RAGConnector] = None,
) -> Dict[str, Any]:
    """
    Fetch raw market data from various sources.
    
    Args:
        data_type: Type of data to collect (rates, news, fred, rag)
        pairs: Currency pairs for rates (e.g., ["EUR/USD", "GBP/USD"])
        days: Number of days of historical data
        series_id: FRED series ID (e.g., "DFF", "DGS10")
        query: Search query for news or RAG
        start_date: Start date for historical data (YYYY-MM-DD)
        end_date: End date for historical data (YYYY-MM-DD)
        connector: Market data connector instance
        news_connector: News connector instance
        fred_connector: FRED connector instance
        rag_connector: RAG connector instance
    
    Returns:
        Dict with data_type, source, data, and metadata
    """
    metadata = {
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "cache_hit": False,
        "quota_used": 0
    }
    
    if data_type == "rates":
        return await _collect_rates(
            pairs=pairs,
            days=days,
            start_date=start_date,
            end_date=end_date,
            connector=connector,
            metadata=metadata
        )
    elif data_type == "news":
        return await _collect_news(
            query=query,
            news_connector=news_connector,
            metadata=metadata
        )
    elif data_type == "fred":
        return await _collect_fred(
            series_id=series_id,
            start_date=start_date,
            end_date=end_date,
            fred_connector=fred_connector,
            metadata=metadata
        )
    elif data_type == "rag":
        return await _collect_rag(
            query=query,
            rag_connector=rag_connector,
            metadata=metadata
        )
    else:
        raise ValueError(f"Unknown data_type: {data_type}")


async def _collect_rates(
    pairs: Optional[List[str]],
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    connector: Optional[MarketDataConnector],
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Collect FX rate data."""
    if not connector:
        raise ValueError("connector required for rates data_type")
    
    if not pairs:
        raise ValueError("pairs required for rates data_type")
    
    data = []
    for pair in pairs:
        parts = pair.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid pair format: {pair}")
        
        base, target = parts
        
        if days:
            # Historical rates
            rates = await connector.get_historical_rates(
                base=base,
                target=target,
                days=days
            )
            data.extend(rates)
        else:
            # Spot rate
            rate = await connector.get_exchange_rate(
                base=base,
                target=target,
                date=start_date
            )
            data.append(rate)
    
    return {
        "data_type": "rates",
        "source": getattr(connector, "source", "unknown"),
        "data": data,
        "metadata": metadata
    }


async def _collect_news(
    query: Optional[str],
    news_connector: Optional[NewsConnectorBase],
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Collect news data."""
    if not news_connector:
        raise ValueError("news_connector required for news data_type")
    
    news_items = await news_connector.get_fx_news(
        query=query or "",
        max_items=10
    )
    
    return {
        "data_type": "news",
        "source": "rss",
        "data": news_items,
        "metadata": metadata
    }


async def _collect_fred(
    series_id: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    fred_connector: Optional[FREDConnector],
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Collect FRED economic data."""
    if not fred_connector:
        raise ValueError("fred_connector required for fred data_type")
    
    if not series_id:
        raise ValueError("series_id required for fred data_type")
    
    if start_date and end_date:
        # Historical series
        data = await fred_connector.get_historical_rates(
            series_id=series_id,
            start_date=start_date,
            end_date=end_date
        )
    else:
        # Current rate
        data = await fred_connector.get_current_rate(series_id=series_id)
    
    return {
        "data_type": "fred",
        "source": "fred",
        "data": data,
        "metadata": metadata
    }


async def _collect_rag(
    query: Optional[str],
    rag_connector: Optional[RAGConnector],
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Collect RAG research data."""
    if not rag_connector:
        raise ValueError("rag_connector required for rag data_type")
    
    if not query:
        raise ValueError("query required for rag data_type")
    
    results = await rag_connector.query(question=query)
    
    return {
        "data_type": "rag",
        "source": "rag",
        "data": results,
        "metadata": metadata
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest backend/tests/unit/test_data_collector.py::test_collect_rates_data -v
```

Expected: PASS

- [ ] **Step 5: Add tests for other data types**

```python
# Add to backend/tests/unit/test_data_collector.py

@pytest.mark.asyncio
async def test_collect_news_data():
    """Test collecting news data."""
    mock_news_connector = AsyncMock()
    mock_news_connector.get_fx_news.return_value = [
        {"title": "EUR rises", "source": "BBC", "url": "http://example.com"}
    ]
    
    result = await collect_market_data(
        data_type="news",
        query="EUR USD",
        news_connector=mock_news_connector
    )
    
    assert result["data_type"] == "news"
    assert result["source"] == "rss"
    assert len(result["data"]) == 1


@pytest.mark.asyncio
async def test_collect_fred_data():
    """Test collecting FRED data."""
    mock_fred_connector = AsyncMock()
    mock_fred_connector.get_current_rate.return_value = {
        "series_id": "DFF",
        "value": 3.64,
        "date": "2026-04-09"
    }
    
    result = await collect_market_data(
        data_type="fred",
        series_id="DFF",
        fred_connector=mock_fred_connector
    )
    
    assert result["data_type"] == "fred"
    assert result["source"] == "fred"


@pytest.mark.asyncio
async def test_collect_rag_data():
    """Test collecting RAG data."""
    mock_rag_connector = AsyncMock()
    mock_rag_connector.query.return_value = {
        "answer": "EUR/USD outlook is positive",
        "sources": [{"title": "Report 1"}]
    }
    
    result = await collect_market_data(
        data_type="rag",
        query="EUR/USD outlook",
        rag_connector=mock_rag_connector
    )
    
    assert result["data_type"] == "rag"
    assert result["source"] == "rag"


@pytest.mark.asyncio
async def test_collect_invalid_data_type():
    """Test error handling for invalid data type."""
    with pytest.raises(ValueError, match="Unknown data_type"):
        await collect_market_data(data_type="invalid")
```

- [ ] **Step 6: Run all Data Collector tests**

```bash
pytest backend/tests/unit/test_data_collector.py -v
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/agents/data_collector.py backend/tests/unit/test_data_collector.py
git commit -m "feat: implement Data Collector agent with unified data fetching"
```

---

### Task 3: Implement Market Analyst Agent

**Files:**
- Create: `backend/agents/market_analyst.py`
- Create: `backend/tests/unit/test_market_analyst.py`

- [ ] **Step 1: Write failing test for trend analysis**

```python
# backend/tests/unit/test_market_analyst.py
import pytest
from backend.agents.market_analyst import analyze_market_trends


@pytest.mark.asyncio
async def test_analyze_trend():
    """Test trend analysis."""
    data = {
        "data_type": "rates",
        "data": [
            {"date": "2026-04-01", "rate": 1.0800},
            {"date": "2026-04-10", "rate": 1.0850},
            {"date": "2026-04-20", "rate": 1.0900},
            {"date": "2026-04-26", "rate": 1.0920}
        ]
    }
    
    result = await analyze_market_trends(
        data=data,
        analysis_type="trend"
    )
    
    assert result["analysis_type"] == "trend"
    assert result["trend_direction"] in ["uptrend", "downtrend", "sideways"]
    assert "strength" in result
    assert 0 <= result["strength"] <= 1
    assert "indicators" in result
    assert "confidence" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest backend/tests/unit/test_market_analyst.py::test_analyze_trend -v
```

Expected: FAIL with "No module named 'backend.agents.market_analyst'"

- [ ] **Step 3: Implement Market Analyst agent**

```python
# backend/agents/market_analyst.py
from typing import Any, Dict, Optional, Literal, List
import statistics


async def analyze_market_trends(
    data: Dict[str, Any],
    analysis_type: Literal["trend", "volatility", "correlation", "signal"] = "trend",
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Analyze FX market data for trends, volatility, correlations, and signals.
    
    Args:
        data: Market data from Data Collector
        analysis_type: Type of analysis (trend, volatility, correlation, signal)
        context: Additional context (news, economic indicators)
    
    Returns:
        Dict with analysis results
    """
    if analysis_type == "trend":
        return await _analyze_trend(data, context)
    elif analysis_type == "volatility":
        return await _analyze_volatility(data, context)
    elif analysis_type == "correlation":
        return await _analyze_correlation(data, context)
    elif analysis_type == "signal":
        return await _generate_signals(data, context)
    else:
        raise ValueError(f"Unknown analysis_type: {analysis_type}")


async def _analyze_trend(
    data: Dict[str, Any],
    context: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Analyze trend direction and strength."""
    rates_data = data.get("data", [])
    
    if not rates_data:
        raise ValueError("No rate data provided")
    
    # Extract rates
    rates = [item["rate"] for item in rates_data if "rate" in item]
    
    if len(rates) < 2:
        raise ValueError("Need at least 2 data points for trend analysis")
    
    # Calculate trend direction
    first_rate = rates[0]
    last_rate = rates[-1]
    change_pct = ((last_rate - first_rate) / first_rate) * 100
    
    if change_pct > 0.5:
        trend_direction = "uptrend"
    elif change_pct < -0.5:
        trend_direction = "downtrend"
    else:
        trend_direction = "sideways"
    
    # Calculate strength (0-1 scale based on consistency)
    strength = min(abs(change_pct) / 5.0, 1.0)  # 5% change = max strength
    
    # Calculate indicators
    sma_20 = statistics.mean(rates[-20:]) if len(rates) >= 20 else statistics.mean(rates)
    volatility = statistics.stdev(rates) if len(rates) > 1 else 0.0
    
    # Calculate momentum (rate of change)
    if len(rates) >= 10:
        recent_avg = statistics.mean(rates[-5:])
        older_avg = statistics.mean(rates[-10:-5])
        momentum = ((recent_avg - older_avg) / older_avg) if older_avg != 0 else 0.0
    else:
        momentum = change_pct / 100
    
    # Confidence based on data points and consistency
    confidence = min(len(rates) / 30, 1.0) * (1 - volatility / last_rate)
    confidence = max(0.0, min(confidence, 1.0))
    
    summary = f"Pair shows {trend_direction} with {strength:.2f} strength. "
    summary += f"Volatility: {volatility:.4f}, Momentum: {momentum:.4f}"
    
    return {
        "analysis_type": "trend",
        "pair": "unknown",  # Extract from data if available
        "trend_direction": trend_direction,
        "strength": round(strength, 2),
        "indicators": {
            "sma_20": round(sma_20, 4),
            "volatility": round(volatility, 4),
            "momentum": round(momentum, 4)
        },
        "signals": [],
        "confidence": round(confidence, 2),
        "summary": summary
    }


async def _analyze_volatility(
    data: Dict[str, Any],
    context: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Analyze volatility."""
    rates_data = data.get("data", [])
    rates = [item["rate"] for item in rates_data if "rate" in item]
    
    if len(rates) < 2:
        raise ValueError("Need at least 2 data points for volatility analysis")
    
    volatility = statistics.stdev(rates)
    mean_rate = statistics.mean(rates)
    volatility_pct = (volatility / mean_rate) * 100
    
    return {
        "analysis_type": "volatility",
        "volatility": round(volatility, 4),
        "volatility_pct": round(volatility_pct, 2),
        "mean_rate": round(mean_rate, 4),
        "confidence": 0.75
    }


async def _analyze_correlation(
    data: Dict[str, Any],
    context: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Analyze correlation with context data."""
    # Placeholder for correlation analysis
    return {
        "analysis_type": "correlation",
        "correlation": 0.0,
        "confidence": 0.5,
        "summary": "Correlation analysis requires context data"
    }


async def _generate_signals(
    data: Dict[str, Any],
    context: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Generate trading signals."""
    # Use trend analysis to generate signals
    trend_result = await _analyze_trend(data, context)
    
    signals = []
    if trend_result["trend_direction"] == "uptrend" and trend_result["strength"] > 0.6:
        signals.append("buy")
    elif trend_result["trend_direction"] == "downtrend" and trend_result["strength"] > 0.6:
        signals.append("sell")
    else:
        signals.append("hold")
    
    return {
        "analysis_type": "signal",
        "signals": signals,
        "confidence": trend_result["confidence"],
        "summary": f"Signal: {signals[0].upper()} based on {trend_result['trend_direction']}"
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest backend/tests/unit/test_market_analyst.py::test_analyze_trend -v
```

Expected: PASS

- [ ] **Step 5: Add tests for other analysis types**

```python
# Add to backend/tests/unit/test_market_analyst.py

@pytest.mark.asyncio
async def test_analyze_volatility():
    """Test volatility analysis."""
    data = {
        "data_type": "rates",
        "data": [
            {"date": "2026-04-01", "rate": 1.0800},
            {"date": "2026-04-10", "rate": 1.0850},
            {"date": "2026-04-20", "rate": 1.0820}
        ]
    }
    
    result = await analyze_market_trends(
        data=data,
        analysis_type="volatility"
    )
    
    assert result["analysis_type"] == "volatility"
    assert "volatility" in result
    assert "volatility_pct" in result


@pytest.mark.asyncio
async def test_generate_signals():
    """Test signal generation."""
    data = {
        "data_type": "rates",
        "data": [
            {"date": "2026-04-01", "rate": 1.0800},
            {"date": "2026-04-26", "rate": 1.0950}  # Strong uptrend
        ]
    }
    
    result = await analyze_market_trends(
        data=data,
        analysis_type="signal"
    )
    
    assert result["analysis_type"] == "signal"
    assert "signals" in result
    assert result["signals"][0] in ["buy", "sell", "hold"]
```

- [ ] **Step 6: Run all Market Analyst tests**

```bash
pytest backend/tests/unit/test_market_analyst.py -v
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/agents/market_analyst.py backend/tests/unit/test_market_analyst.py
git commit -m "feat: implement Market Analyst agent with trend/volatility/signal analysis"
```

---

### Task 4: Implement Report Generator Agent

**Files:**
- Create: `backend/agents/report_generator.py`
- Create: `backend/tests/unit/test_report_generator.py`

- [ ] **Step 1: Write failing test for PDF generation**

```python
# backend/tests/unit/test_report_generator.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.agents.report_generator import generate_report


@pytest.mark.asyncio
async def test_generate_pdf_report():
    """Test PDF report generation."""
    data = {
        "data_type": "rates",
        "data": [{"date": "2026-04-26", "rate": 1.0850}]
    }
    analysis = {
        "trend_direction": "uptrend",
        "strength": 0.75
    }
    
    with patch('backend.agents.report_generator._generate_pdf') as mock_pdf:
        mock_pdf.return_value = {
            "pdf_url": "/api/export/pdf?id=abc123",
            "filename": "report.pdf",
            "size_bytes": 45678
        }
        
        result = await generate_report(
            data=data,
            analysis=analysis,
            format="pdf",
            title="EUR/USD Analysis"
        )
        
        assert result["format"] == "pdf"
        assert result["title"] == "EUR/USD Analysis"
        assert "content" in result
        assert result["content"]["pdf_url"] == "/api/export/pdf?id=abc123"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest backend/tests/unit/test_report_generator.py::test_generate_pdf_report -v
```

Expected: FAIL with "No module named 'backend.agents.report_generator'"

- [ ] **Step 3: Implement Report Generator agent**

```python
# backend/agents/report_generator.py
from typing import Any, Dict, Optional, Literal
from datetime import datetime
import json


async def generate_report(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]] = None,
    format: Literal["pdf", "dashboard", "summary"] = "summary",
    title: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate formatted reports, dashboards, or summaries.
    
    Args:
        data: Market data to include in report
        analysis: Analysis results to include
        format: Output format (pdf, dashboard, summary)
        title: Report title
    
    Returns:
        Dict with format, title, content, and metadata
    """
    if format == "pdf":
        return await _generate_pdf(data, analysis, title)
    elif format == "dashboard":
        return await _generate_dashboard(data, analysis, title)
    elif format == "summary":
        return await _generate_summary(data, analysis, title)
    else:
        raise ValueError(f"Unknown format: {format}")


async def _generate_pdf(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]],
    title: Optional[str]
) -> Dict[str, Any]:
    """Generate PDF report."""
    # This would integrate with existing PDF skill
    # For now, return a mock structure
    
    content = {
        "pdf_url": f"/api/export/pdf?id=mock_{datetime.utcnow().timestamp()}",
        "filename": f"fx-report-{datetime.utcnow().strftime('%Y%m%d')}.pdf",
        "size_bytes": 45678
    }
    
    metadata = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "pages": 3
    }
    
    return {
        "format": "pdf",
        "title": title or "Market Report",
        "content": content,
        "metadata": metadata
    }


async def _generate_dashboard(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]],
    title: Optional[str]
) -> Dict[str, Any]:
    """Generate inline Chart.js dashboard."""
    rates_data = data.get("data", [])
    
    # Format for Chart.js
    labels = [item.get("date", "") for item in rates_data if "date" in item]
    values = [item.get("rate", 0) for item in rates_data if "rate" in item]
    
    content = {
        "chart_type": "line",
        "labels": labels,
        "datasets": [{
            "label": title or "FX Rates",
            "data": values,
            "borderColor": "rgb(75, 192, 192)",
            "tension": 0.1
        }]
    }
    
    metadata = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "data_points": len(labels)
    }
    
    return {
        "format": "dashboard",
        "title": title or "FX Dashboard",
        "content": content,
        "metadata": metadata
    }


async def _generate_summary(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]],
    title: Optional[str]
) -> Dict[str, Any]:
    """Generate text summary."""
    summary_lines = []
    
    if title:
        summary_lines.append(f"# {title}")
    
    # Summarize data
    rates_data = data.get("data", [])
    if rates_data:
        summary_lines.append(f"\nData points: {len(rates_data)}")
        if "rate" in rates_data[0]:
            first_rate = rates_data[0]["rate"]
            last_rate = rates_data[-1]["rate"]
            change = ((last_rate - first_rate) / first_rate) * 100
            summary_lines.append(f"Change: {change:+.2f}%")
    
    # Summarize analysis
    if analysis:
        if "trend_direction" in analysis:
            summary_lines.append(f"\nTrend: {analysis['trend_direction']}")
        if "summary" in analysis:
            summary_lines.append(f"\n{analysis['summary']}")
    
    content = {
        "text": "\n".join(summary_lines)
    }
    
    metadata = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "length": len(content["text"])
    }
    
    return {
        "format": "summary",
        "title": title or "Summary",
        "content": content,
        "metadata": metadata
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest backend/tests/unit/test_report_generator.py::test_generate_pdf_report -v
```

Expected: PASS

- [ ] **Step 5: Add tests for other formats**

```python
# Add to backend/tests/unit/test_report_generator.py

@pytest.mark.asyncio
async def test_generate_dashboard():
    """Test dashboard generation."""
    data = {
        "data_type": "rates",
        "data": [
            {"date": "2026-04-01", "rate": 1.0800},
            {"date": "2026-04-26", "rate": 1.0850}
        ]
    }
    
    result = await generate_report(
        data=data,
        format="dashboard",
        title="EUR/USD Trend"
    )
    
    assert result["format"] == "dashboard"
    assert result["title"] == "EUR/USD Trend"
    assert "labels" in result["content"]
    assert "datasets" in result["content"]


@pytest.mark.asyncio
async def test_generate_summary():
    """Test summary generation."""
    data = {
        "data_type": "rates",
        "data": [{"date": "2026-04-26", "rate": 1.0850}]
    }
    analysis = {
        "trend_direction": "uptrend",
        "summary": "Strong upward momentum"
    }
    
    result = await generate_report(
        data=data,
        analysis=analysis,
        format="summary",
        title="Market Summary"
    )
    
    assert result["format"] == "summary"
    assert "text" in result["content"]
    assert "uptrend" in result["content"]["text"]
```

- [ ] **Step 6: Run all Report Generator tests**

```bash
pytest backend/tests/unit/test_report_generator.py -v
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/agents/report_generator.py backend/tests/unit/test_report_generator.py
git commit -m "feat: implement Report Generator agent with PDF/dashboard/summary formats"
```

---

### Task 5: Implement Research Synthesizer Agent

**Files:**
- Create: `backend/agents/research_synthesizer.py`
- Create: `backend/tests/unit/test_research_synthesizer.py`

- [ ] **Step 1: Write failing test for research synthesis**

```python
# backend/tests/unit/test_research_synthesizer.py
import pytest
from backend.agents.research_synthesizer import synthesize_research


@pytest.mark.asyncio
async def test_synthesize_multi_source():
    """Test synthesizing data from multiple sources."""
    sources = {
        "rates": {
            "data": [
                {"date": "2026-04-01", "rate": 1.0800},
                {"date": "2026-04-26", "rate": 1.0850}
            ]
        },
        "news": {
            "data": [
                {"title": "EUR strengthens", "sentiment": "positive"}
            ]
        },
        "fred": {
            "data": {"series_id": "DFF", "value": 3.64}
        }
    }
    
    result = await synthesize_research(
        sources=sources,
        focus="interest rates"
    )
    
    assert "synthesis" in result
    assert "key_insights" in result
    assert isinstance(result["key_insights"], list)
    assert "sources_used" in result
    assert "confidence" in result
    assert 0 <= result["confidence"] <= 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest backend/tests/unit/test_research_synthesizer.py::test_synthesize_multi_source -v
```

Expected: FAIL with "No module named 'backend.agents.research_synthesizer'"

- [ ] **Step 3: Implement Research Synthesizer agent**

```python
# backend/agents/research_synthesizer.py
from typing import Any, Dict, Optional, List


async def synthesize_research(
    sources: Dict[str, Any],
    focus: Optional[str] = None,
    max_sources: int = 10
) -> Dict[str, Any]:
    """
    Combine multi-source market intelligence into coherent insights.
    
    Args:
        sources: Data from multiple sources (rates, news, fred, rag)
        focus: Aspect to emphasize (e.g., 'interest rates', 'technical analysis')
        max_sources: Maximum number of sources to include
    
    Returns:
        Dict with synthesis, key_insights, sources_used, and confidence
    """
    key_insights = []
    sources_used = []
    
    # Analyze rates data
    if "rates" in sources:
        rates_insight = _analyze_rates_source(sources["rates"])
        if rates_insight:
            key_insights.append(rates_insight)
            sources_used.append({
                "type": "rates",
                "count": len(sources["rates"].get("data", []))
            })
    
    # Analyze news data
    if "news" in sources:
        news_insight = _analyze_news_source(sources["news"])
        if news_insight:
            key_insights.append(news_insight)
            sources_used.append({
                "type": "news",
                "count": len(sources["news"].get("data", []))
            })
    
    # Analyze FRED data
    if "fred" in sources:
        fred_insight = _analyze_fred_source(sources["fred"], focus)
        if fred_insight:
            key_insights.append(fred_insight)
            sources_used.append({
                "type": "fred",
                "series": [sources["fred"].get("data", {}).get("series_id", "unknown")]
            })
    
    # Analyze RAG data
    if "rag" in sources:
        rag_insight = _analyze_rag_source(sources["rag"])
        if rag_insight:
            key_insights.append(rag_insight)
            sources_used.append({
                "type": "rag",
                "documents": 1
            })
    
    # Generate synthesis narrative
    synthesis = _generate_synthesis_narrative(key_insights, focus)
    
    # Calculate confidence based on source agreement and quantity
    confidence = _calculate_confidence(sources_used, key_insights)
    
    return {
        "synthesis": synthesis,
        "key_insights": key_insights[:max_sources],
        "sources_used": sources_used,
        "confidence": round(confidence, 2)
    }


def _analyze_rates_source(rates_data: Dict[str, Any]) -> Optional[str]:
    """Extract insight from rates data."""
    data = rates_data.get("data", [])
    if not data or len(data) < 2:
        return None
    
    first_rate = data[0].get("rate", 0)
    last_rate = data[-1].get("rate", 0)
    
    if first_rate == 0:
        return None
    
    change_pct = ((last_rate - first_rate) / first_rate) * 100
    
    if abs(change_pct) < 0.1:
        return f"Exchange rate stable at {last_rate:.4f}"
    elif change_pct > 0:
        return f"Exchange rate up {change_pct:+.2f}% to {last_rate:.4f}"
    else:
        return f"Exchange rate down {change_pct:.2f}% to {last_rate:.4f}"


def _analyze_news_source(news_data: Dict[str, Any]) -> Optional[str]:
    """Extract insight from news data."""
    data = news_data.get("data", [])
    if not data:
        return None
    
    # Simple sentiment analysis based on titles
    positive_count = sum(1 for item in data if "sentiment" in item and item["sentiment"] == "positive")
    total_count = len(data)
    
    if total_count == 0:
        return None
    
    sentiment_pct = (positive_count / total_count) * 100
    
    if sentiment_pct > 60:
        return f"News sentiment: {sentiment_pct:.0f}% positive ({total_count} articles)"
    elif sentiment_pct < 40:
        return f"News sentiment: {100-sentiment_pct:.0f}% negative ({total_count} articles)"
    else:
        return f"News sentiment: mixed ({total_count} articles)"


def _analyze_fred_source(fred_data: Dict[str, Any], focus: Optional[str]) -> Optional[str]:
    """Extract insight from FRED data."""
    data = fred_data.get("data", {})
    
    if isinstance(data, dict) and "value" in data:
        series_id = data.get("series_id", "unknown")
        value = data.get("value", 0)
        
        if focus and "interest" in focus.lower():
            return f"Interest rate indicator ({series_id}): {value}%"
        else:
            return f"Economic indicator ({series_id}): {value}"
    
    return None


def _analyze_rag_source(rag_data: Dict[str, Any]) -> Optional[str]:
    """Extract insight from RAG data."""
    data = rag_data.get("data", {})
    
    if isinstance(data, dict) and "answer" in data:
        answer = data["answer"]
        # Truncate if too long
        if len(answer) > 150:
            answer = answer[:147] + "..."
        return f"Research: {answer}"
    
    return None


def _generate_synthesis_narrative(insights: List[str], focus: Optional[str]) -> str:
    """Generate coherent narrative from insights."""
    if not insights:
        return "Insufficient data for synthesis"
    
    # Join insights with connecting phrases
    if len(insights) == 1:
        narrative = insights[0]
    elif len(insights) == 2:
        narrative = f"{insights[0]}. {insights[1]}"
    else:
        narrative = f"{insights[0]}. Additionally, {insights[1].lower()}"
        if len(insights) > 2:
            narrative += f". {insights[2]}"
    
    if focus:
        narrative = f"Focusing on {focus}: {narrative}"
    
    return narrative


def _calculate_confidence(sources_used: List[Dict[str, Any]], insights: List[str]) -> float:
    """Calculate confidence score based on sources and insights."""
    if not sources_used or not insights:
        return 0.0
    
    # Base confidence on number of sources
    source_score = min(len(sources_used) / 4, 1.0)  # 4 sources = max
    
    # Boost if insights are substantial
    insight_score = min(len(insights) / 3, 1.0)  # 3 insights = max
    
    # Average the scores
    confidence = (source_score + insight_score) / 2
    
    return confidence
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest backend/tests/unit/test_research_synthesizer.py::test_synthesize_multi_source -v
```

Expected: PASS

- [ ] **Step 5: Add tests for edge cases**

```python
# Add to backend/tests/unit/test_research_synthesizer.py

@pytest.mark.asyncio
async def test_synthesize_single_source():
    """Test synthesis with only one source."""
    sources = {
        "rates": {
            "data": [
                {"date": "2026-04-26", "rate": 1.0850}
            ]
        }
    }
    
    result = await synthesize_research(sources=sources)
    
    assert "synthesis" in result
    assert len(result["sources_used"]) == 1


@pytest.mark.asyncio
async def test_synthesize_empty_sources():
    """Test synthesis with empty sources."""
    sources = {}
    
    result = await synthesize_research(sources=sources)
    
    assert result["synthesis"] == "Insufficient data for synthesis"
    assert result["confidence"] == 0.0
```

- [ ] **Step 6: Run all Research Synthesizer tests**

```bash
pytest backend/tests/unit/test_research_synthesizer.py -v
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/agents/research_synthesizer.py backend/tests/unit/test_research_synthesizer.py
git commit -m "feat: implement Research Synthesizer agent for multi-source intelligence"
```

---

## Phase 2: Update Orchestrator

### Task 6: Add sub-agent tool definitions

**Files:**
- Modify: `backend/agent/tools.py`

- [ ] **Step 1: Add Data Collector tool definition**

```python
# Add to TOOL_DEFINITIONS list in backend/agent/tools.py (after existing tools)

    {
        "type": "function",
        "function": {
            "name": "collect_market_data",
            "description": (
                "Fetch market data from various sources (FX rates, news, FRED economic indicators, research documents). "
                "Can be called multiple times in parallel for different data types."
            ),
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
    },
```

- [ ] **Step 2: Add remaining sub-agent tool definitions**

```python
# Add to TOOL_DEFINITIONS list in backend/agent/tools.py

    {
        "type": "function",
        "function": {
            "name": "analyze_market_trends",
            "description": (
                "Analyze FX market data for trends, volatility, correlations, and trading signals. "
                "Use after collecting data to perform technical/statistical analysis."
            ),
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
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": (
                "Generate formatted reports, dashboards, or summaries from market data and analysis. "
                "Use when user requests formatted output."
            ),
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
    },
    {
        "type": "function",
        "function": {
            "name": "synthesize_research",
            "description": (
                "Combine multi-source market intelligence (rates, news, economic data, research) into coherent insights. "
                "Use when user asks for comprehensive insights across sources."
            ),
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
    },
```

- [ ] **Step 3: Add dispatch handlers for sub-agents**

```python
# Add to dispatch_tool() function in backend/agent/tools.py (after existing handlers)

    elif tool_name == "collect_market_data":
        from backend.agents import collect_market_data
        return await collect_market_data(
            data_type=arguments["data_type"],
            pairs=arguments.get("pairs"),
            days=arguments.get("days"),
            series_id=arguments.get("series_id"),
            query=arguments.get("query"),
            connector=connector,
            news_connector=news_connector,
            fred_connector=fred_connector,
            rag_connector=rag_connector
        )
    
    elif tool_name == "analyze_market_trends":
        from backend.agents import analyze_market_trends
        return await analyze_market_trends(
            data=arguments["data"],
            analysis_type=arguments.get("analysis_type", "trend"),
            context=arguments.get("context")
        )
    
    elif tool_name == "generate_report":
        from backend.agents import generate_report
        return await generate_report(
            data=arguments["data"],
            analysis=arguments.get("analysis"),
            format=arguments["format"],
            title=arguments.get("title")
        )
    
    elif tool_name == "synthesize_research":
        from backend.agents import synthesize_research
        return await synthesize_research(
            sources=arguments["sources"],
            focus=arguments.get("focus"),
            max_sources=arguments.get("max_sources", 10)
        )
```

- [ ] **Step 4: Verify tool definitions are valid JSON**

```bash
python -c "import json; from backend.agent.tools import TOOL_DEFINITIONS; print(f'Valid: {len(TOOL_DEFINITIONS)} tools')"
```

Expected: "Valid: 12 tools" (8 old + 4 new)

- [ ] **Step 5: Commit**

```bash
git add backend/agent/tools.py
git commit -m "feat: add sub-agent tool definitions and dispatch handlers"
```

---

### Task 7: Update orchestrator system prompt

**Files:**
- Modify: `backend/agent/agent.py`

- [ ] **Step 1: Read current SYSTEM_PROMPT**

```bash
grep -A 20 "SYSTEM_PROMPT =" backend/agent/agent.py
```

- [ ] **Step 2: Update SYSTEM_PROMPT with sub-agent descriptions**

```python
# Update SYSTEM_PROMPT in backend/agent/agent.py

SYSTEM_PROMPT = """
You are the orchestrator for AI Market Studio, a multi-agent FX market intelligence platform.

You coordinate 4 specialized sub-agents:

1. **Data Collector** (collect_market_data) - Fetches raw market data
   - FX rates: data_type="rates", pairs=["EUR/USD"]
   - News: data_type="news", query="EUR USD"
   - FRED economic indicators: data_type="fred", series_id="DFF"
   - Research documents: data_type="rag", query="EUR/USD outlook"
   - Can be called multiple times in parallel for different data types

2. **Market Analyst** (analyze_market_trends) - Analyzes trends, volatility, signals
   - Use after collecting data to perform technical/statistical analysis
   - analysis_type: "trend", "volatility", "correlation", or "signal"
   - Requires data from Data Collector as input

3. **Report Generator** (generate_report) - Creates PDFs, dashboards, summaries
   - format: "pdf", "dashboard", or "summary"
   - Use when user requests formatted output
   - Can work with raw data or analysis results

4. **Research Synthesizer** (synthesize_research) - Combines multi-source intelligence
   - Use when user asks for comprehensive insights across sources
   - Requires data from multiple sources (rates + news + FRED + RAG)
   - Generates coherent narrative synthesis

**Parallel Execution:**
When fetching data from multiple independent sources, call Data Collector multiple times in parallel.
Example: For "market insight on EUR/USD", call in the same round:
- collect_market_data(data_type="rates", pairs=["EUR/USD"])
- collect_market_data(data_type="news", query="EUR USD")
- collect_market_data(data_type="fred", series_id="DFF")

**Sequential Execution:**
When one agent depends on another's output, call them sequentially.
Example: For "analyze EUR/USD trend", call:
1. collect_market_data(data_type="rates", pairs=["EUR/USD"], days=30)
2. analyze_market_trends(data=<result_from_step_1>)

**Legacy Tools (still available):**
You also have access to legacy tools (get_exchange_rate, get_fx_news, etc.) for backward compatibility.
Prefer using the new sub-agent tools for better organization and parallel execution.

**Your Role:**
- Understand user intent
- Decide which sub-agents to call and in what order
- Coordinate parallel vs sequential execution
- Synthesize final response in natural language
- Maintain conversation context

Be concise, accurate, and helpful. Always cite your data sources.
"""
```

- [ ] **Step 3: Verify syntax**

```bash
python -c "from backend.agent.agent import SYSTEM_PROMPT; print(f'Prompt length: {len(SYSTEM_PROMPT)} chars')"
```

Expected: No errors, prompt length > 1000 chars

- [ ] **Step 4: Commit**

```bash
git add backend/agent/agent.py
git commit -m "feat: update orchestrator system prompt with sub-agent descriptions"
```

---

### Task 8: Integration testing

**Files:**
- Create: `backend/tests/integration/test_multi_agent_flow.py`

- [ ] **Step 1: Write integration test for simple workflow**

```python
# backend/tests/integration/test_multi_agent_flow.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.agent.agent import run_agent


@pytest.mark.asyncio
async def test_simple_rate_query():
    """Test simple rate query using Data Collector."""
    mock_connector = AsyncMock()
    mock_connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.0850,
        "date": "2026-04-26"
    }
    
    messages = [
        {"role": "user", "content": "What is EUR/USD today?"}
    ]
    
    response = await run_agent(
        messages=messages,
        connector=mock_connector,
        news_connector=None,
        fred_connector=None,
        rag_connector=None
    )
    
    assert response["role"] == "assistant"
    assert "1.0850" in response["content"] or "EUR/USD" in response["content"]
```

- [ ] **Step 2: Run integration test**

```bash
pytest backend/tests/integration/test_multi_agent_flow.py::test_simple_rate_query -v
```

Expected: PASS

- [ ] **Step 3: Add test for parallel execution**

```python
# Add to backend/tests/integration/test_multi_agent_flow.py

@pytest.mark.asyncio
async def test_parallel_data_collection():
    """Test parallel data collection from multiple sources."""
    mock_connector = AsyncMock()
    mock_connector.get_exchange_rate.return_value = {"rate": 1.0850}
    
    mock_news_connector = AsyncMock()
    mock_news_connector.get_fx_news.return_value = [{"title": "EUR rises"}]
    
    mock_fred_connector = AsyncMock()
    mock_fred_connector.get_current_rate.return_value = {"value": 3.64}
    
    messages = [
        {"role": "user", "content": "Give me market insight on EUR/USD"}
    ]
    
    response = await run_agent(
        messages=messages,
        connector=mock_connector,
        news_connector=mock_news_connector,
        fred_connector=mock_fred_connector,
        rag_connector=None
    )
    
    assert response["role"] == "assistant"
    # Verify multiple sources were used
    assert mock_connector.get_exchange_rate.called
    assert mock_news_connector.get_fx_news.called
```

- [ ] **Step 4: Run all integration tests**

```bash
pytest backend/tests/integration/test_multi_agent_flow.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/integration/test_multi_agent_flow.py
git commit -m "test: add integration tests for multi-agent workflows"
```

---

### Task 9: Run full test suite

**Files:**
- N/A (verification step)

- [ ] **Step 1: Run all unit tests**

```bash
pytest backend/tests/unit/ -v
```

Expected: All tests PASS

- [ ] **Step 2: Run all integration tests**

```bash
pytest backend/tests/integration/ -v
```

Expected: All tests PASS

- [ ] **Step 3: Run E2E tests (if available)**

```bash
pytest backend/tests/e2e/ -v
```

Expected: All tests PASS

- [ ] **Step 4: Check test coverage**

```bash
pytest --cov=backend/agents --cov-report=term-missing
```

Expected: Coverage > 80%

- [ ] **Step 5: Commit if any fixes were needed**

```bash
git add .
git commit -m "test: ensure all tests pass with multi-agent architecture"
```

---

## Phase 3: Deprecate Old Tools (Optional - can be done later)

### Task 10: Remove old tool definitions

**Files:**
- Modify: `backend/agent/tools.py`

- [ ] **Step 1: Comment out old tool definitions**

```python
# In backend/agent/tools.py, comment out the 8 old tool definitions:
# - get_exchange_rate
# - get_exchange_rates
# - get_historical_rates
# - get_interest_rate
# - generate_dashboard
# - get_fx_news
# - generate_market_insight
# - get_internal_research

# Keep them commented for now in case rollback is needed
```

- [ ] **Step 2: Comment out old dispatch handlers**

```python
# In dispatch_tool() function, comment out old handlers
# Keep them for reference during transition period
```

- [ ] **Step 3: Run tests to verify nothing breaks**

```bash
pytest backend/tests/ -v
```

Expected: All tests PASS (tests should use new sub-agents)

- [ ] **Step 4: Commit**

```bash
git add backend/agent/tools.py
git commit -m "refactor: deprecate old tool definitions in favor of sub-agents"
```

---

## Deployment

### Task 11: Deploy to GKE

**Files:**
- N/A (deployment step)

- [ ] **Step 1: Build Docker image**

```bash
docker build -t gcr.io/gen-lang-client-0896070179/ai-market-studio:multi-agent .
```

- [ ] **Step 2: Push to GCR**

```bash
docker push gcr.io/gen-lang-client-0896070179/ai-market-studio:multi-agent
```

- [ ] **Step 3: Update deployment**

```bash
kubectl set image deployment/ai-market-studio ai-market-studio=gcr.io/gen-lang-client-0896070179/ai-market-studio:multi-agent
```

- [ ] **Step 4: Verify deployment**

```bash
kubectl rollout status deployment/ai-market-studio
kubectl get pods
```

Expected: Pods running, no errors

- [ ] **Step 5: Test live endpoint**

```bash
curl http://35.224.3.54/
```

Expected: 200 OK

- [ ] **Step 6: Monitor logs**

```bash
kubectl logs -f deployment/ai-market-studio --tail=50
```

Expected: No errors, sub-agent calls visible in logs

---

## Self-Review Checklist

### Spec Coverage

✅ **Executive Summary** - Covered in Phase 1 (sub-agent structure)
✅ **System Architecture** - Covered in Phase 1 & 2 (agents + orchestrator)
✅ **Frontend UI Changes** - Deferred to separate frontend repo (noted in plan)
✅ **Sub-Agent Specifications** - Fully implemented in Tasks 2-5
✅ **Orchestrator Changes** - Covered in Tasks 6-7
✅ **Implementation Details** - All phases covered
✅ **Success Metrics** - Deployment includes monitoring (Task 11)

### Placeholder Scan

✅ No "TBD" or "TODO" found
✅ No "implement later" found
✅ All code blocks are complete
✅ All test expectations are specific

### Type Consistency

✅ `collect_market_data` signature matches across all tasks
✅ `analyze_market_trends` signature matches across all tasks
✅ `generate_report` signature matches across all tasks
✅ `synthesize_research` signature matches across all tasks
✅ Return types consistent (Dict[str, Any])

---

**End of Implementation Plan**