"""Test to verify the market insight fix works correctly."""
import asyncio
from backend.agents.data_collector import collect_market_data
from backend.agents.research_synthesizer import synthesize_research
from backend.connectors.mock_connector import MockConnector
from backend.connectors.news_connector import MockNewsConnector


async def test_market_insight_workflow():
    """Test the complete workflow: collect data -> synthesize."""
    print("Testing: 'Give me a market insight on EUR/USD and GBP/USD'")
    print("=" * 60)

    # Step 1: Collect rates data (parallel)
    print("\n1. Collecting rates data...")
    rates_result = await collect_market_data(
        data_type='rates',
        pairs=['EUR/USD', 'GBP/USD'],
        connector=MockConnector()
    )
    print(f"   [OK] Collected {len(rates_result['data'])} rates")

    # Step 2: Collect news data (parallel)
    print("\n2. Collecting news data...")
    news_result = await collect_market_data(
        data_type='news',
        query='EUR USD GBP',
        news_connector=MockNewsConnector()
    )
    print(f"   [OK] Collected {len(news_result['data'])} news items")

    # Step 3: Synthesize research
    print("\n3. Synthesizing research...")
    sources = {
        'rates': rates_result,
        'news': news_result
    }

    result = await synthesize_research(sources=sources)

    print(f"   [OK] Synthesis complete")
    print(f"\n{'=' * 60}")
    print(f"RESULT:")
    print(f"{'=' * 60}")
    print(f"Synthesis: {result['synthesis']}")
    print(f"Key Insights: {result['key_insights']}")
    print(f"Sources Used: {result['sources_used']}")
    print(f"Confidence: {result['confidence']}")

    # Verify the fix
    assert result['synthesis'] != "Insufficient data for synthesis", \
        "ERROR: Still getting 'Insufficient data for synthesis'!"
    assert len(result['key_insights']) > 0, \
        "ERROR: No insights generated!"
    assert result['confidence'] > 0, \
        "ERROR: Zero confidence!"

    print(f"\n{'=' * 60}")
    print("PASS: Market insight workflow works correctly!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(test_market_insight_workflow())
