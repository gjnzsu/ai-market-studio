"""Test that all agent functions are properly exported."""

import pytest


def test_all_agents_importable():
    """Verify all agent functions can be imported from backend.agents."""
    from backend.agents import (
        collect_market_data,
        analyze_market_trends,
        generate_report,
        synthesize_research
    )

    # Verify they are callable
    assert callable(collect_market_data)
    assert callable(analyze_market_trends)
    assert callable(generate_report)
    assert callable(synthesize_research)


def test_agents_all_list():
    """Verify __all__ exports match actual functions."""
    from backend.agents import __all__

    expected = [
        "collect_market_data",
        "analyze_market_trends",
        "generate_report",
        "synthesize_research"
    ]

    assert set(__all__) == set(expected)
