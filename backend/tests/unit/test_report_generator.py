import pytest
from unittest.mock import AsyncMock, patch
from backend.agents.report_generator import generate_report


@pytest.mark.asyncio
async def test_generate_pdf_report():
    """Test PDF report generation."""
    data = {
        "data_type": "rates",
        "data": [{"date": "2026-04-26", "rate": 1.0850}]
    }
    analysis = {
        "trend_direction": "uptrend",
        "strength": 0.75
    }

    result = await generate_report(
        data=data,
        analysis=analysis,
        format="pdf",
        title="EUR/USD Analysis"
    )

    assert result["format"] == "pdf"
    assert result["title"] == "EUR/USD Analysis"
    assert "content" in result
    assert "pdf_url" in result["content"]
    assert "filename" in result["content"]
    assert "metadata" in result
    assert "generated_at" in result["metadata"]


@pytest.mark.asyncio
async def test_generate_dashboard():
    """Test dashboard generation."""
    data = {
        "data_type": "rates",
        "data": [
            {"date": "2026-04-01", "rate": 1.0800},
            {"date": "2026-04-26", "rate": 1.0850}
        ]
    }

    result = await generate_report(
        data=data,
        format="dashboard",
        title="EUR/USD Trend"
    )

    assert result["format"] == "dashboard"
    assert result["title"] == "EUR/USD Trend"
    assert "labels" in result["content"]
    assert "datasets" in result["content"]
    assert len(result["content"]["labels"]) == 2
    assert result["content"]["labels"][0] == "2026-04-01"
    assert result["content"]["datasets"][0]["data"][0] == 1.0800


@pytest.mark.asyncio
async def test_generate_summary():
    """Test summary generation."""
    data = {
        "data_type": "rates",
        "data": [{"date": "2026-04-26", "rate": 1.0850}]
    }
    analysis = {
        "trend_direction": "uptrend",
        "summary": "Strong upward momentum"
    }

    result = await generate_report(
        data=data,
        analysis=analysis,
        format="summary",
        title="Market Summary"
    )

    assert result["format"] == "summary"
    assert "text" in result["content"]
    assert "uptrend" in result["content"]["text"]
    assert "Strong upward momentum" in result["content"]["text"]


@pytest.mark.asyncio
async def test_generate_report_invalid_format():
    """Test error handling for invalid format."""
    data = {"data": [{"rate": 1.0850}]}

    with pytest.raises(ValueError, match="Unknown format: invalid"):
        await generate_report(data=data, format="invalid")


@pytest.mark.asyncio
async def test_generate_report_empty_data():
    """Test error handling for empty data."""
    with pytest.raises(ValueError, match="data parameter cannot be empty"):
        await generate_report(data={}, format="summary")


@pytest.mark.asyncio
async def test_generate_report_none_data():
    """Test error handling for None data."""
    with pytest.raises(ValueError, match="data parameter cannot be empty"):
        await generate_report(data=None, format="summary")


@pytest.mark.asyncio
async def test_generate_summary_with_zero_first_rate():
    """Test summary generation handles zero first_rate gracefully."""
    data = {
        "data": [
            {"date": "2026-04-01", "rate": 0.0},
            {"date": "2026-04-26", "rate": 1.0850}
        ]
    }

    result = await generate_report(data=data, format="summary")

    assert result["format"] == "summary"
    assert "N/A (base rate is zero)" in result["content"]["text"]


@pytest.mark.asyncio
async def test_generate_summary_with_empty_rates_data():
    """Test summary generation with empty rates data."""
    data = {"data": []}

    result = await generate_report(data=data, format="summary")

    assert result["format"] == "summary"
    assert "text" in result["content"]
    # Should not crash, just return minimal summary


@pytest.mark.asyncio
async def test_generate_summary_with_missing_rate_key():
    """Test summary generation when rate key is missing."""
    data = {
        "data": [
            {"date": "2026-04-01"},  # No 'rate' key
            {"date": "2026-04-26"}
        ]
    }

    result = await generate_report(data=data, format="summary")

    assert result["format"] == "summary"
    assert "Data points: 2" in result["content"]["text"]
    # Should not crash, just skip change calculation


@pytest.mark.asyncio
async def test_generate_dashboard_with_empty_data():
    """Test dashboard generation with empty data."""
    data = {"data": []}

    result = await generate_report(data=data, format="dashboard")

    assert result["format"] == "dashboard"
    assert result["content"]["labels"] == []
    assert result["content"]["datasets"][0]["data"] == []
    assert result["metadata"]["data_points"] == 0


@pytest.mark.asyncio
async def test_generate_report_uses_default_titles():
    """Test that default titles are used when title is None."""
    data = {"data": [{"rate": 1.0850}]}

    pdf_result = await generate_report(data=data, format="pdf")
    assert pdf_result["title"] == "Market Report"

    dashboard_result = await generate_report(data=data, format="dashboard")
    assert dashboard_result["title"] == "Market Dashboard"

    summary_result = await generate_report(data=data, format="summary")
    assert summary_result["title"] == "Market Summary"

