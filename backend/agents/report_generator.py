from typing import Any, Dict, Optional, Literal
from datetime import datetime, timezone
import json


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
    """
    if format == "pdf":
        return await _generate_pdf(data, analysis, title)
    elif format == "dashboard":
        return await _generate_dashboard(data, analysis, title)
    elif format == "summary":
        return await _generate_summary(data, analysis, title)
    else:
        raise ValueError(f"Unknown format: {format}")


async def _generate_pdf(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]],
    title: Optional[str]
) -> Dict[str, Any]:
    """Generate PDF report."""
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
        "title": title or "Market Report",
        "content": content,
        "metadata": metadata
    }


async def _generate_dashboard(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]],
    title: Optional[str]
) -> Dict[str, Any]:
    """Generate inline Chart.js dashboard."""
    rates_data = data.get("data", [])

    # Format for Chart.js
    labels = [item.get("date", "") for item in rates_data if "date" in item]
    values = [item.get("rate", 0) for item in rates_data if "rate" in item]

    content = {
        "chart_type": "line",
        "labels": labels,
        "datasets": [{
            "label": title or "FX Rates",
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
        "title": title or "FX Dashboard",
        "content": content,
        "metadata": metadata
    }


async def _generate_summary(
    data: Dict[str, Any],
    analysis: Optional[Dict[str, Any]],
    title: Optional[str]
) -> Dict[str, Any]:
    """Generate text summary."""
    summary_lines = []

    if title:
        summary_lines.append(f"# {title}")

    # Summarize data
    rates_data = data.get("data", [])
    if rates_data:
        summary_lines.append(f"\nData points: {len(rates_data)}")
        if "rate" in rates_data[0]:
            first_rate = rates_data[0]["rate"]
            last_rate = rates_data[-1]["rate"]
            change = ((last_rate - first_rate) / first_rate) * 100
            summary_lines.append(f"Change: {change:+.2f}%")

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
        "title": title or "Summary",
        "content": content,
        "metadata": metadata
    }
