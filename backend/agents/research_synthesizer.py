"""
Research Synthesizer Agent

Combines multi-source market intelligence (rates, news, FRED, RAG) into coherent insights.
Part of the multi-agent architecture for AI Market Studio.

Key responsibilities:
- Analyze data from multiple sources (rates, news, fred, rag)
- Extract key insights from each source
- Generate synthesis narrative with focus area support
- Calculate confidence scores based on source agreement and quantity
"""

import logging
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)


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

    Raises:
        ValueError: If max_sources is less than 1
    """
    if max_sources < 1:
        raise ValueError("max_sources must be at least 1")

    logger.info(f"Synthesizing research from {len(sources)} sources with focus: {focus}")

    key_insights = []
    sources_used = []

    try:
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

        logger.info(f"Synthesis complete: {len(key_insights)} insights, confidence={confidence:.2f}")

        return {
            "synthesis": synthesis,
            "key_insights": key_insights[:max_sources],
            "sources_used": sources_used,
            "confidence": round(confidence, 2)
        }

    except Exception as e:
        logger.error(f"Error during research synthesis: {e}", exc_info=True)
        raise


def _analyze_rates_source(rates_data: Dict[str, Any]) -> Optional[str]:
    """Extract insight from rates data."""
    try:
        data = rates_data.get("data", [])
        if not data:
            return None

        # Handle single data point
        if len(data) == 1:
            rate = data[0].get("rate", 0)
            if rate == 0:
                return None
            return f"Exchange rate at {rate:.4f}"

        # Handle multiple data points
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

    except (KeyError, TypeError, ZeroDivisionError) as e:
        logger.warning(f"Error analyzing rates source: {e}")
        return None


def _analyze_news_source(news_data: Dict[str, Any]) -> Optional[str]:
    """Extract insight from news data."""
    try:
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

    except (KeyError, TypeError, ZeroDivisionError) as e:
        logger.warning(f"Error analyzing news source: {e}")
        return None


def _analyze_fred_source(fred_data: Dict[str, Any], focus: Optional[str]) -> Optional[str]:
    """Extract insight from FRED data."""
    try:
        data = fred_data.get("data", {})

        if isinstance(data, dict) and "value" in data:
            series_id = data.get("series_id", "unknown")
            value = data.get("value", 0)

            if focus and "interest" in focus.lower():
                return f"Interest rate indicator ({series_id}): {value}%"
            else:
                return f"Economic indicator ({series_id}): {value}"

        return None

    except (KeyError, TypeError) as e:
        logger.warning(f"Error analyzing FRED source: {e}")
        return None


def _analyze_rag_source(rag_data: Dict[str, Any]) -> Optional[str]:
    """Extract insight from RAG data."""
    try:
        data = rag_data.get("data", {})

        if isinstance(data, dict) and "answer" in data:
            answer = data["answer"]
            # Truncate if too long
            if len(answer) > 150:
                answer = answer[:147] + "..."
            return f"Research: {answer}"

        return None

    except (KeyError, TypeError) as e:
        logger.warning(f"Error analyzing RAG source: {e}")
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
