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
