"""
E2E tests for PDF export functionality.

Tests the /api/export/pdf endpoint with various data types:
- Simple exchange rate data
- Multiple rates (insight type)
- Dashboard data
- News data
- RAG sources

Verifies that:
1. PDF files are generated successfully
2. Response has correct content-type
3. PDF content is valid (can be parsed)
4. Different data types are handled correctly
"""
import pytest
from io import BytesIO
from pypdf import PdfReader


def test_export_simple_rate_to_pdf(app_client):
    """Test PDF export with simple exchange rate data."""
    payload = {
        "reply": "The EUR/USD rate is 1.0868 as of 2026-04-18.",
        "data": {
            "base": "EUR",
            "target": "USD",
            "rate": 1.0868,
            "date": "2026-04-18",
            "source": "mock"
        },
        "tool_used": "get_exchange_rate"
    }

    response = app_client.post("/api/export/pdf", json=payload)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers.get("content-disposition", "")
    assert "fx-insight-" in response.headers.get("content-disposition", "")

    # Verify it's a valid PDF
    pdf_content = BytesIO(response.content)
    reader = PdfReader(pdf_content)
    assert len(reader.pages) >= 1

    # Check PDF contains expected text
    page_text = reader.pages[0].extract_text()
    assert "AI Market Studio" in page_text
    assert "Summary" in page_text


def test_export_insight_data_to_pdf(app_client):
    """Test PDF export with insight type data (multiple rates)."""
    payload = {
        "reply": "Here are the current FX rates for EUR and GBP against USD.",
        "data": {
            "type": "insight",
            "rates": [
                {
                    "base": "EUR",
                    "target": "USD",
                    "rate": 1.0868,
                    "date": "2026-04-18"
                },
                {
                    "base": "GBP",
                    "target": "USD",
                    "rate": 1.2729,
                    "date": "2026-04-18"
                }
            ]
        },
        "tool_used": "get_multiple_rates"
    }

    response = app_client.post("/api/export/pdf", json=payload)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    # Verify PDF structure
    pdf_content = BytesIO(response.content)
    reader = PdfReader(pdf_content)
    page_text = reader.pages[0].extract_text()

    assert "FX Rates" in page_text
    assert "Summary" in page_text


def test_export_dashboard_data_to_pdf(app_client):
    """Test PDF export with dashboard type data."""
    payload = {
        "reply": "Dashboard data for EUR/USD over the past week.",
        "data": {
            "type": "dashboard",
            "panel_type": "line_trend",
            "base": "EUR",
            "targets": ["USD", "GBP"],
            "start_date": "2026-04-11",
            "end_date": "2026-04-18",
            "series": [
                {"date": "2026-04-11", "rates": {"USD": 1.0850, "GBP": 0.8520}},
                {"date": "2026-04-12", "rates": {"USD": 1.0860, "GBP": 0.8525}},
                {"date": "2026-04-18", "rates": {"USD": 1.0868, "GBP": 0.8530}}
            ]
        },
        "tool_used": "get_dashboard_data"
    }

    response = app_client.post("/api/export/pdf", json=payload)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    pdf_content = BytesIO(response.content)
    reader = PdfReader(pdf_content)
    page_text = reader.pages[0].extract_text()

    assert "Dashboard Data" in page_text


def test_export_news_data_to_pdf(app_client):
    """Test PDF export with news type data."""
    payload = {
        "reply": "Latest FX market news headlines.",
        "data": {
            "type": "news",
            "items": [
                {
                    "title": "EUR/USD rises on ECB policy expectations",
                    "source": "Reuters",
                    "published": "2026-04-18"
                },
                {
                    "title": "GBP strengthens against USD",
                    "source": "Bloomberg",
                    "published": "2026-04-18"
                }
            ]
        },
        "tool_used": "get_market_news"
    }

    response = app_client.post("/api/export/pdf", json=payload)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    pdf_content = BytesIO(response.content)
    reader = PdfReader(pdf_content)
    page_text = reader.pages[0].extract_text()

    assert "News Headlines" in page_text or "Market News" in page_text


def test_export_rag_sources_to_pdf(app_client):
    """Test PDF export with RAG sources."""
    payload = {
        "reply": "Based on internal research documents, the EUR/USD outlook is positive.",
        "data": {
            "type": "rag",
            "sources": [
                {"name": "Q1-2026-FX-Report.pdf"},
                {"name": "ECB-Policy-Analysis.pdf"}
            ]
        },
        "tool_used": "get_internal_research"
    }

    response = app_client.post("/api/export/pdf", json=payload)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    pdf_content = BytesIO(response.content)
    reader = PdfReader(pdf_content)
    page_text = reader.pages[0].extract_text()

    assert "Sources" in page_text


def test_export_minimal_data_to_pdf(app_client):
    """Test PDF export with minimal data (reply only)."""
    payload = {
        "reply": "The current market conditions are stable.",
        "data": None,
        "tool_used": None
    }

    response = app_client.post("/api/export/pdf", json=payload)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    # Should still generate a valid PDF with just the summary
    pdf_content = BytesIO(response.content)
    reader = PdfReader(pdf_content)
    assert len(reader.pages) >= 1

    page_text = reader.pages[0].extract_text()
    assert "Summary" in page_text
    assert "stable" in page_text


def test_export_pdf_file_size_reasonable(app_client):
    """Test that generated PDFs are reasonably sized."""
    payload = {
        "reply": "Test reply",
        "data": {"base": "EUR", "target": "USD", "rate": 1.0868},
        "tool_used": "test"
    }

    response = app_client.post("/api/export/pdf", json=payload)

    assert response.status_code == 200

    # PDF should be between 1KB and 100KB for simple data
    pdf_size = len(response.content)
    assert 1000 < pdf_size < 100000, f"PDF size {pdf_size} bytes is outside expected range"


def test_export_pdf_invalid_data_handled(app_client):
    """Test that invalid data doesn't crash the PDF generator."""
    payload = {
        "reply": "Test with malformed data",
        "data": {"type": "unknown_type", "invalid_field": "test"},
        "tool_used": "test"
    }

    response = app_client.post("/api/export/pdf", json=payload)

    # Should still generate a PDF (graceful degradation)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

