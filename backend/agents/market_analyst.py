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
