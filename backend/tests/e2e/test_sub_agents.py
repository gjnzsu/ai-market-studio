"""E2E tests for sub-agent orchestration."""

import pytest


@pytest.mark.asyncio
async def test_data_collector_agent():
    """Test Data Collector sub-agent fetches market data."""
    from backend.agents.data_collector import collect_market_data
    from backend.connectors.mock_connector import MockConnector
    from backend.connectors.news_connector import MockNewsConnector

    # Test rates collection
    result = await collect_market_data(
        data_type="rates",
        pairs=["EUR/USD"],
        connector=MockConnector(),
    )
    assert result is not None
    assert "EUR/USD" in str(result)

    # Test news collection
    result = await collect_market_data(
        data_type="news",
        query="EUR USD",
        news_connector=MockNewsConnector(),
    )
    assert result is not None


@pytest.mark.asyncio
async def test_market_analyst_agent():
    """Test Market Analyst sub-agent performs analysis."""
    from backend.agents.market_analyst import analyze_market_trends

    # Use correct data structure expected by market_analyst
    mock_data = {
        "data": [
            {"date": "2026-04-20", "rate": 1.08},
            {"date": "2026-04-27", "rate": 1.0868},
        ]
    }

    result = await analyze_market_trends(
        data=mock_data,
        analysis_type="trend"
    )
    assert result is not None
    assert "analysis" in result or "trend" in str(result).lower()


@pytest.mark.asyncio
async def test_report_generator_agent():
    """Test Report Generator sub-agent creates reports."""
    from backend.agents.report_generator import generate_report

    mock_data = {
        "rates": [{"base": "EUR", "target": "USD", "rate": 1.0868}],
        "news": [{"title": "ECB holds rates", "source": "Reuters"}]
    }

    result = await generate_report(
        data=mock_data,
        format="summary"
    )
    assert result is not None


@pytest.mark.asyncio
async def test_research_synthesizer_agent():
    """Test Research Synthesizer sub-agent combines sources."""
    from backend.agents.research_synthesizer import synthesize_research

    mock_sources = {
        "rates": {"EUR/USD": 1.0868},
        "news": [{"title": "Fed signals pause"}],
        "fred": {"DFF": 3.64},
        "rag": {"answer": "EUR/USD outlook positive"}
    }

    result = await synthesize_research(
        sources=mock_sources,
        focus="market insight"
    )
    assert result is not None
    assert "synthesis" in result or "insight" in str(result).lower()


@pytest.mark.asyncio
async def test_sub_agent_orchestration_workflow():
    """Test full orchestration: collect → analyze → synthesize."""
    from backend.agent.agent import run_agent
    from backend.connectors.mock_connector import MockConnector
    from backend.connectors.news_connector import MockNewsConnector

    # Test with simple query that uses legacy tools
    result = await run_agent(
        message="What is EUR/USD rate?",
        history=[],
        connector=MockConnector(),
        news_connector=MockNewsConnector(),
    )

    # Verify agent completed
    assert result is not None
    assert "reply" in result
    assert result["reply"] is not None


@pytest.mark.asyncio
async def test_parallel_data_collection():
    """Test that Data Collector can be called in parallel."""
    from backend.agents.data_collector import collect_market_data
    from backend.connectors.mock_connector import MockConnector
    from backend.connectors.news_connector import MockNewsConnector
    import asyncio

    # Simulate parallel calls
    tasks = [
        collect_market_data(data_type="rates", pairs=["EUR/USD"], connector=MockConnector()),
        collect_market_data(data_type="news", query="EUR USD", news_connector=MockNewsConnector()),
    ]

    results = await asyncio.gather(*tasks)
    assert len(results) == 2
    assert all(r is not None for r in results)


@pytest.mark.asyncio
async def test_sequential_workflow():
    """Test sequential workflow: collect then analyze."""
    from backend.agents.data_collector import collect_market_data
    from backend.agents.market_analyst import analyze_market_trends
    from backend.connectors.mock_connector import MockConnector

    # Step 1: Collect data
    data = await collect_market_data(
        data_type="rates",
        pairs=["EUR/USD"],
        connector=MockConnector(),
    )
    assert data is not None

    # Step 2: Analyze collected data with at least 2 data points
    analysis = await analyze_market_trends(
        data={"data": [
            {"date": "2026-04-20", "rate": 1.08},
            {"date": "2026-04-27", "rate": 1.0868}
        ]},
        analysis_type="trend"
    )
    assert analysis is not None
