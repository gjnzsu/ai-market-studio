"""Report Generator Agent - formats market data and analysis into reports.

Generates formatted outputs in multiple formats:
- PDF: Export-ready payload for the backend PDF export endpoint
- Dashboard: Chart.js-compatible visualization data
- Summary: Human-readable text summary

Routes requests by format parameter and returns structured payloads with metadata.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

logger = logging.getLogger(__name__)

DEFAULT_TITLES = {
    "pdf": "Market Report",
    "dashboard": "Market Dashboard",
    "summary": "Market Summary",
}


async def generate_report(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]] = None,
    format: Literal["pdf", "dashboard", "summary"] = "summary",
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate formatted reports, dashboards, or summaries.

    Args:
        data: Market data to include in report.
        analysis: Analysis results to include.
        format: Output format (pdf, dashboard, summary).
        title: Report title.

    Returns:
        Dict with format, title, content, and metadata.

    Raises:
        ValueError: If format is invalid.
    """
    logger.info("Generating %s report with title: %s", format, title)

    if not data:
        logger.warning("Report data is empty, returning placeholder")
        return {
            "type": "report",
            "format": format,
            "title": title or DEFAULT_TITLES.get(format, "Report"),
            "content": "No data available for report generation.",
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "empty",
            },
        }

    try:
        if format == "pdf":
            return await _generate_pdf(data, analysis, title)
        if format == "dashboard":
            return await _generate_dashboard(data, analysis, title)
        if format == "summary":
            return await _generate_summary(data, analysis, title)

        logger.error("Invalid format requested: %s", format)
        raise ValueError(f"Unknown format: {format}")
    except Exception as exc:
        logger.error("Error generating %s report: %s", format, exc)
        raise


async def _generate_pdf(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]],
    title: Optional[str],
) -> Dict[str, Any]:
    """Return the payload needed to render a PDF through /api/export/pdf."""
    logger.debug("Generating PDF export payload")

    report_title = title or DEFAULT_TITLES["pdf"]
    export_payload = {
        "reply": report_title,
        "data": data,
        "tool_used": "generate_report",
    }
    content = {
        "export_endpoint": "/api/export/pdf",
        "export_payload": export_payload,
        "filename": f"fx-report-{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf",
        "content_type": "application/pdf",
    }
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready_for_export",
        "analysis_included": analysis is not None,
    }

    return {
        "format": "pdf",
        "title": report_title,
        "content": content,
        "metadata": metadata,
    }


async def _generate_dashboard(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]],
    title: Optional[str],
) -> Dict[str, Any]:
    """Generate inline Chart.js dashboard."""
    logger.debug("Generating dashboard report")

    rates_data = data.get("data", [])
    labels = [item.get("date", "") for item in rates_data if "date" in item]
    values = [item.get("rate", 0) for item in rates_data if "rate" in item]

    content = {
        "chart_type": "line",
        "labels": labels,
        "datasets": [
            {
                "label": title or DEFAULT_TITLES["dashboard"],
                "data": values,
                "borderColor": "rgb(75, 192, 192)",
                "tension": 0.1,
            }
        ],
    }
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_points": len(labels),
    }

    return {
        "format": "dashboard",
        "title": title or DEFAULT_TITLES["dashboard"],
        "content": content,
        "metadata": metadata,
    }


async def _generate_summary(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]],
    title: Optional[str],
) -> Dict[str, Any]:
    """Generate text summary."""
    logger.debug("Generating summary report")

    summary_lines = []
    if title:
        summary_lines.append(f"# {title}")

    rates_data = data.get("data", [])
    if rates_data:
        summary_lines.append(f"\nData points: {len(rates_data)}")
        if len(rates_data) > 0 and "rate" in rates_data[0]:
            first_rate = rates_data[0]["rate"]
            last_rate = rates_data[-1]["rate"]
            if first_rate != 0:
                change = ((last_rate - first_rate) / first_rate) * 100
                summary_lines.append(f"Change: {change:+.2f}%")
            else:
                logger.warning("Cannot calculate change: first_rate is zero")
                summary_lines.append("Change: N/A (base rate is zero)")

    if analysis:
        if "trend_direction" in analysis:
            summary_lines.append(f"\nTrend: {analysis['trend_direction']}")
        if "summary" in analysis:
            summary_lines.append(f"\n{analysis['summary']}")

    content = {"text": "\n".join(summary_lines)}
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "length": len(content["text"]),
    }

    return {
        "format": "summary",
        "title": title or DEFAULT_TITLES["summary"],
        "content": content,
        "metadata": metadata,
    }
