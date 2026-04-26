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


@pytest.mark.asyncio
async def test_synthesize_with_rag_source():
    """Test synthesis including RAG data."""
    sources = {
        "rag": {
            "data": {
                "answer": "The Federal Reserve is expected to maintain rates."
            }
        }
    }

    result = await synthesize_research(sources=sources)

    assert "synthesis" in result
    assert len(result["key_insights"]) == 1
    assert "Research:" in result["key_insights"][0]


@pytest.mark.asyncio
async def test_synthesize_max_sources_limit():
    """Test that max_sources parameter limits insights."""
    sources = {
        "rates": {"data": [{"date": "2026-04-01", "rate": 1.0800}, {"date": "2026-04-26", "rate": 1.0850}]},
        "news": {"data": [{"title": "EUR strengthens", "sentiment": "positive"}]},
        "fred": {"data": {"series_id": "DFF", "value": 3.64}},
        "rag": {"data": {"answer": "Market analysis shows positive trends."}}
    }

    result = await synthesize_research(sources=sources, max_sources=2)

    assert len(result["key_insights"]) <= 2


@pytest.mark.asyncio
async def test_synthesize_invalid_max_sources():
    """Test that invalid max_sources raises ValueError."""
    sources = {"rates": {"data": [{"date": "2026-04-26", "rate": 1.0850}]}}

    with pytest.raises(ValueError, match="max_sources must be at least 1"):
        await synthesize_research(sources=sources, max_sources=0)


@pytest.mark.asyncio
async def test_synthesize_malformed_rates_data():
    """Test handling of malformed rates data."""
    sources = {
        "rates": {
            "data": [
                {"date": "2026-04-01"},  # Missing rate
                {"date": "2026-04-26", "rate": 1.0850}
            ]
        }
    }

    result = await synthesize_research(sources=sources)

    # Should handle gracefully without crashing
    assert "synthesis" in result
    assert "confidence" in result


@pytest.mark.asyncio
async def test_synthesize_news_sentiment_analysis():
    """Test news sentiment analysis with different ratios."""
    # Test positive sentiment
    sources_positive = {
        "news": {
            "data": [
                {"title": "Good news 1", "sentiment": "positive"},
                {"title": "Good news 2", "sentiment": "positive"},
                {"title": "Bad news", "sentiment": "negative"}
            ]
        }
    }

    result = await synthesize_research(sources=sources_positive)
    assert "positive" in result["key_insights"][0]

    # Test negative sentiment
    sources_negative = {
        "news": {
            "data": [
                {"title": "Bad news 1", "sentiment": "negative"},
                {"title": "Bad news 2", "sentiment": "negative"},
                {"title": "Good news", "sentiment": "positive"}
            ]
        }
    }

    result = await synthesize_research(sources=sources_negative)
    assert "negative" in result["key_insights"][0]
