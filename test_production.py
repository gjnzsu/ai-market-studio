#!/usr/bin/env python3
"""Test production deployment with all pre-defined scenarios."""

import requests
import json
import sys

BACKEND_URL = "http://35.224.3.54/api"

TEST_SCENARIOS = [
    {
        "name": "FRED - Federal Funds Rate",
        "message": "What is the current Federal Funds Rate?"
    },
    {
        "name": "FX Rate - EUR/USD",
        "message": "What is the current EUR/USD exchange rate?"
    },
    {
        "name": "FX News",
        "message": "What's the latest news on EUR/USD?"
    },
    {
        "name": "Market Insight",
        "message": "Give me a market insight for EUR/USD and GBP/USD"
    },
    {
        "name": "Historical Rates",
        "message": "Show me EUR/USD rates for the last 7 days"
    }
]


def test_scenario(scenario):
    """Test a single scenario against production API."""
    print(f"\n{'='*80}")
    print(f"TEST: {scenario['name']}")
    print(f"{'='*80}")
    print(f"Message: {scenario['message']}")

    try:
        response = requests.post(
            f"{BACKEND_URL}/chat",
            json={"message": scenario['message'], "history": []},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            print(f"\n[OK] Status: {response.status_code}")
            print(f"Tool Used: {data.get('tool_used')}")
            print(f"Reply: {data['reply'][:200]}..." if len(data['reply']) > 200 else f"Reply: {data['reply']}")
            return True
        else:
            print(f"\n[FAIL] Status: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        return False


def main():
    """Run all production tests."""
    print("\n" + "="*80)
    print("AI MARKET STUDIO - PRODUCTION TEST SUITE")
    print(f"Backend URL: {BACKEND_URL}")
    print("="*80)

    results = []
    for scenario in TEST_SCENARIOS:
        passed = test_scenario(scenario)
        results.append((scenario['name'], passed))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "[PASSED]" if passed else "[FAILED]"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed_count}/{total_count} scenarios passed")

    if passed_count == total_count:
        print("\n[SUCCESS] ALL PRODUCTION TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n[ERROR] SOME PRODUCTION TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
