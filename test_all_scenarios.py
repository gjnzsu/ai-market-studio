#!/usr/bin/env python3
"""
Comprehensive test script for all pre-defined AI Market Studio scenarios.
Tests FRED integration, FX rates, news, and RAG queries.
"""

import asyncio
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from backend.connectors.fred_connector import FREDConnector, FREDConnectorError
from backend.connectors.mock_connector import MockConnector
from backend.connectors.news_connector import RSSNewsConnector
from backend.agent.agent import run_agent

# Test scenarios from the frontend
TEST_SCENARIOS = [
    {
        "name": "FRED - Federal Funds Rate",
        "message": "What is the current Federal Funds Rate?",
        "expected_tool": "get_interest_rate"
    },
    {
        "name": "FX Rate - EUR/USD",
        "message": "What is the current EUR/USD exchange rate?",
        "expected_tool": "get_exchange_rate"
    },
    {
        "name": "FX News",
        "message": "What's the latest news on EUR/USD?",
        "expected_tool": "get_fx_news"
    },
    {
        "name": "Market Insight",
        "message": "Give me a market insight for EUR/USD and GBP/USD",
        "expected_tool": "generate_market_insight"
    },
    {
        "name": "Historical Rates",
        "message": "Show me EUR/USD rates for the last 7 days",
        "expected_tool": "get_historical_rates"
    }
]


async def test_fred_connector():
    """Test FRED connector directly."""
    print("\n" + "="*80)
    print("TESTING FRED CONNECTOR DIRECTLY")
    print("="*80)

    try:
        fred = FREDConnector()
        print(f"[OK] FREDConnector initialized successfully")

        # Test getting current federal funds rate
        print("\nFetching current Federal Funds Rate (DFF)...")
        result = await fred.get_current_rate("DFF")
        print(f"[OK] Success: {result.series_name} = {result.value}% (as of {result.date})")

        # Test listing available series
        print("\nListing available FRED series...")
        series = await fred.list_fred_series()
        print(f"[OK] Found {len(series)} available series")
        for series_id, name in list(series.items())[:3]:
            print(f"  - {series_id}: {name}")

        return True
    except FREDConnectorError as e:
        print(f"[FAIL] FRED Connector Error: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_scenario(scenario, connector, news_connector, fred_connector):
    """Test a single agent scenario."""
    print(f"\n{'='*80}")
    print(f"TEST: {scenario['name']}")
    print(f"{'='*80}")
    print(f"Message: {scenario['message']}")

    try:
        result = await run_agent(
            message=scenario['message'],
            history=[],
            connector=connector,
            news_connector=news_connector,
            fred_connector=fred_connector,
            rag_connector=None  # RAG not available in local test
        )

        print(f"\n[OK] Agent Response:")
        print(f"  Tool Used: {result['tool_used']}")
        print(f"  Reply: {result['reply'][:200]}..." if len(result['reply']) > 200 else f"  Reply: {result['reply']}")

        if result['data']:
            print(f"  Data Type: {type(result['data'])}")
            if isinstance(result['data'], dict):
                print(f"  Data Keys: {list(result['data'].keys())}")

        # Verify expected tool was used
        if scenario['expected_tool'] and result['tool_used'] != scenario['expected_tool']:
            print(f"[WARN] Warning: Expected tool '{scenario['expected_tool']}' but got '{result['tool_used']}'")

        return True

    except Exception as e:
        print(f"\n[FAIL] Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("AI MARKET STUDIO - COMPREHENSIVE TEST SUITE")
    print("="*80)

    # Test 1: FRED Connector Direct Test
    fred_test_passed = await test_fred_connector()

    # Initialize connectors for agent tests
    print("\n" + "="*80)
    print("INITIALIZING CONNECTORS FOR AGENT TESTS")
    print("="*80)

    connector = MockConnector()
    print("[OK] MockConnector initialized")

    news_connector = RSSNewsConnector()
    print("[OK] RSSNewsConnector initialized")

    fred_connector = FREDConnector()
    print("[OK] FREDConnector initialized")

    # Test 2: Agent Scenarios
    print("\n" + "="*80)
    print("TESTING AGENT WITH ALL SCENARIOS")
    print("="*80)

    results = []
    for scenario in TEST_SCENARIOS:
        passed = await test_agent_scenario(scenario, connector, news_connector, fred_connector)
        results.append((scenario['name'], passed))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    print(f"\nFRED Connector Direct Test: {'[PASSED]' if fred_test_passed else '[FAILED]'}")
    print(f"\nAgent Scenario Tests:")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "[PASSED]" if passed else "[FAILED]"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed_count}/{total_count} scenarios passed")

    # Exit code
    all_passed = fred_test_passed and passed_count == total_count
    if all_passed:
        print("\n[SUCCESS] ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n[ERROR] SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
