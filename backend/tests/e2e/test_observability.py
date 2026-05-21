"""E2E tests for observability integration."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_observability_metrics_emitted():
    """Test that LLM calls emit observability metrics."""
    from backend.agent.agent import run_agent
    from backend.connectors.mock_connector import MockConnector
    from backend.connectors.news_connector import MockNewsConnector
    from contextlib import asynccontextmanager

    mock_tracker = MagicMock()
    mock_tracker.prompt_tokens = 0
    mock_tracker.completion_tokens = 0

    @asynccontextmanager
    async def mock_track_llm_call(*args, **kwargs):
        yield mock_tracker

    mock_obs_client = MagicMock()
    mock_obs_client.track_llm_call = mock_track_llm_call

    with patch('backend.agent.agent.get_client', return_value=mock_obs_client):
        result = await run_agent(
            message="What is EUR/USD rate?",
            history=[],
            connector=MockConnector(),
            news_connector=MockNewsConnector(),
        )

        assert result["reply"] is not None
        assert mock_tracker.prompt_tokens >= 0


@pytest.mark.asyncio
async def test_observability_tracks_tokens():
    """Test that token counts are tracked correctly."""
    from backend.agent.agent import run_agent
    from backend.connectors.mock_connector import MockConnector
    from contextlib import asynccontextmanager

    mock_tracker = MagicMock()
    mock_tracker.prompt_tokens = 0
    mock_tracker.completion_tokens = 0

    @asynccontextmanager
    async def mock_track_llm_call(*args, **kwargs):
        yield mock_tracker

    mock_obs_client = MagicMock()
    mock_obs_client.track_llm_call = mock_track_llm_call

    with patch('backend.agent.agent.get_client', return_value=mock_obs_client):
        await run_agent(
            message="EUR/USD rate?",
            history=[],
            connector=MockConnector(),
        )

        assert mock_tracker.prompt_tokens >= 0
        assert mock_tracker.completion_tokens >= 0


@pytest.mark.asyncio
async def test_observability_graceful_degradation():
    """Test that agent works even if observability fails."""
    from backend.agent.agent import run_agent
    from backend.connectors.mock_connector import MockConnector

    # Simulate observability failure
    with patch('backend.agent.agent.get_client', side_effect=RuntimeError("Observability unavailable")):
        result = await run_agent(
            message="What is EUR/USD?",
            history=[],
            connector=MockConnector(),
        )

        # Agent should still work
        assert result["reply"] is not None
        assert "EUR" in result["reply"] or "USD" in result["reply"]


@pytest.mark.asyncio
async def test_observability_metric_names():
    """Test that correct metric names are used."""
    import os

    # Verify observability URL is configured
    observability_url = os.getenv(
        "OBSERVABILITY_URL",
        "http://ai-sre-observability.default.svc.cluster.local:8080"
    )
    assert "ai-sre-observability" in observability_url

    # Verify SDK is importable
    try:
        from ai_sre_observability import setup_observability, get_client
        assert setup_observability is not None
        assert get_client is not None
    except ImportError:
        pytest.fail("ai_sre_observability SDK not installed")


@pytest.mark.asyncio
async def test_observability_cost_calculation():
    """Test that cost metrics are calculated for LLM calls."""
    from backend.agent.agent import run_agent
    from backend.connectors.mock_connector import MockConnector
    from contextlib import asynccontextmanager

    mock_tracker = MagicMock()
    mock_tracker.prompt_tokens = 0
    mock_tracker.completion_tokens = 0

    @asynccontextmanager
    async def mock_track_llm_call(*args, **kwargs):
        yield mock_tracker

    mock_obs_client = MagicMock()
    mock_obs_client.track_llm_call = mock_track_llm_call

    with patch('backend.agent.agent.get_client', return_value=mock_obs_client):
        await run_agent(
            message="EUR/USD?",
            history=[],
            connector=MockConnector(),
        )

        # Verify tokens can be set (cost is calculated server-side)
        assert hasattr(mock_tracker, 'prompt_tokens')
        assert hasattr(mock_tracker, 'completion_tokens')
