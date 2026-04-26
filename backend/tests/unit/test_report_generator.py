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

    with patch('backend.agents.report_generator._generate_pdf') as mock_pdf:
        mock_pdf.return_value = {
            "format": "pdf",
            "title": "EUR/USD Analysis",
            "content": {
                "pdf_url": "/api/export/pdf?id=abc123",
                "filename": "report.pdf",
                "size_bytes": 45678
            },
            "metadata": {
                "generated_at": "2026-04-26T12:00:00Z",
                "pages": 3
            }
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
        assert result["content"]["pdf_url"] == "/api/export/pdf?id=abc123"


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
