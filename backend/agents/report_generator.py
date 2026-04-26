"""Report Generator Agent — formats market data and analysis into reports.

Generates formatted outputs in multiple formats:
- PDF: Export-ready report structure (integrates with PDF skill)
- Dashboard: Chart.js-compatible visualization data
- Summary: Human-readable text summary

Routes requests by format parameter and returns structured payloads with metadata.
"""

import logging
from typing import Any, Dict, Optional, Literal
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Default titles for each format
DEFAULT_TITLES = {
    "pdf": "Market Report",
    "dashboard": "Market Dashboard",
    "summary": "Market Summary"
}


async def generate_report(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]] = None,
    format: Literal["pdf", "dashboard", "summary"] = "summary",
    title: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate formatted reports, dashboards, or summaries.

    Args:
        data: Market data to include in report
        analysis: Analysis results to include
        format: Output format (pdf, dashboard, summary)
        title: Report title

    Returns:
        Dict with format, title, content, and metadata

    Raises:
        ValueError: If format is invalid or data is empty
    """
    logger.info(f"Generating {format} report with title: {title}")

    if not data:
        logger.error("Cannot generate report: data is empty")
        raise ValueError("data parameter cannot be empty")

    try:
        if format == "pdf":
            return await _generate_pdf(data, analysis, title)
        elif format == "dashboard":
            return await _generate_dashboard(data, analysis, title)
        elif format == "summary":
            return await _generate_summary(data, analysis, title)
        else:
            logger.error(f"Invalid format requested: {format}")
            raise ValueError(f"Unknown format: {format}")
    except Exception as e:
        logger.error(f"Error generating {format} report: {e}")
        raise


async def _generate_pdf(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]],
    title: Optional[str]
) -> Dict[str, Any]:
    """Generate PDF report."""
    logger.debug("Generating PDF report")

    # This would integrate with existing PDF skill
    # For now, return a mock structure

    content = {
        "pdf_url": f"/api/export/pdf?id=mock_{datetime.now(timezone.utc).timestamp()}",
        "filename": f"fx-report-{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf",
        "size_bytes": 45678
    }

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pages": 3
    }

    return {
        "format": "pdf",
        "title": title or DEFAULT_TITLES["pdf"],
        "content": content,
        "metadata": metadata
    }


async def _generate_dashboard(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]],
    title: Optional[str]
) -> Dict[str, Any]:
    """Generate inline Chart.js dashboard."""
    logger.debug("Generating dashboard report")

    rates_data = data.get("data", [])

    # Format for Chart.js
    labels = [item.get("date", "") for item in rates_data if "date" in item]
    values = [item.get("rate", 0) for item in rates_data if "rate" in item]

    content = {
        "chart_type": "line",
        "labels": labels,
        "datasets": [{
            "label": title or DEFAULT_TITLES["dashboard"],
            "data": values,
            "borderColor": "rgb(75, 192, 192)",
            "tension": 0.1
        }]
    }

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_points": len(labels)
    }

    return {
        "format": "dashboard",
        "title": title or DEFAULT_TITLES["dashboard"],
        "content": content,
        "metadata": metadata
    }


async def _generate_summary(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]],
    title: Optional[str]
) -> Dict[str, Any]:
    """Generate text summary."""
    logger.debug("Generating summary report")

    summary_lines = []

    if title:
        summary_lines.append(f"# {title}")

    # Summarize data
    rates_data = data.get("data", [])
    if rates_data:
        summary_lines.append(f"\nData points: {len(rates_data)}")

        # Defensive: check if rates_data has items and first item has 'rate' key
        if len(rates_data) > 0 and "rate" in rates_data[0]:
            first_rate = rates_data[0]["rate"]
            last_rate = rates_data[-1]["rate"]

            # Defensive: prevent division by zero
            if first_rate != 0:
                change = ((last_rate - first_rate) / first_rate) * 100
                summary_lines.append(f"Change: {change:+.2f}%")
            else:
                logger.warning("Cannot calculate change: first_rate is zero")
                summary_lines.append("Change: N/A (base rate is zero)")

    # Summarize analysis
    if analysis:
        if "trend_direction" in analysis:
            summary_lines.append(f"\nTrend: {analysis['trend_direction']}")
        if "summary" in analysis:
            summary_lines.append(f"\n{analysis['summary']}")

    content = {
        "text": "\n".join(summary_lines)
    }

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "length": len(content["text"])
    }

    return {
        "format": "summary",
        "title": title or DEFAULT_TITLES["summary"],
        "content": content,
        "metadata": metadata
    }
