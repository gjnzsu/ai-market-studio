"""
PDF exporter for AI Market Studio chat responses.
Renders structured FX market insights as a formatted PDF document.
"""
import io
from datetime import datetime
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


BRAND_PRIMARY = colors.HexColor("#1A3A5C")   # deep navy
BRAND_ACCENT  = colors.HexColor("#2E7D9B")   # teal
BRAND_LIGHT   = colors.HexColor("#F0F4F8")   # light gray-blue
TEXT_BODY     = colors.HexColor("#222222")
TEXT_MUTED    = colors.HexColor("#666666")


def _styles():
    s = getSampleStyleSheet()
    base = s["Normal"]
    base.textColor = TEXT_BODY
    base.fontName = "Helvetica"

    title_style = ParagraphStyle(
        "DocTitle",
        parent=s["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=BRAND_PRIMARY,
        spaceAfter=4,
        leading=28,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=base,
        fontName="Helvetica",
        fontSize=11,
        textColor=TEXT_MUTED,
        spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "SectionHead",
        parent=s["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=BRAND_PRIMARY,
        spaceBefore=14,
        spaceAfter=6,
        leading=18,
    )
    body_style = ParagraphStyle(
        "DocBody",
        parent=base,
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        spaceAfter=6,
    )
    muted_style = ParagraphStyle(
        "Muted",
        parent=base,
        fontName="Helvetica-Oblique",
        fontSize=9,
        textColor=TEXT_MUTED,
        spaceAfter=4,
    )
    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=base,
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.white,
    )
    return {
        "title": title_style,
        "subtitle": subtitle_style,
        "section": section_style,
        "body": body_style,
        "muted": muted_style,
        "table_header": table_header_style,
    }


def _build_header(story, meta, styles):
    """Logo area + title block."""
    story.append(Paragraph("AI Market Studio", styles["title"]))
    story.append(Paragraph("FX Market Intelligence Report", styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=BRAND_ACCENT, spaceAfter=8))
    if meta.get("generated_at"):
        story.append(Paragraph(
            f"Generated: {meta['generated_at']}  |  Tool: {meta.get('tool_used', 'N/A')}",
            styles["muted"]
        ))
    story.append(Spacer(1, 6 * mm))


def _build_rates_table(rates: list[dict], styles) -> Optional[Table]:
    """Build a rates table from insight data."""
    if not rates:
        return None

    header_style = styles["table_header"]
    rows = [
        [
            Paragraph("Pair", header_style),
            Paragraph("Rate", header_style),
            Paragraph("Date", header_style),
        ]
    ]
    for r in rates:
        if r.get("error"):
            rows.append([
                Paragraph(f"{r['base']}/{r['target']}", styles["body"]),
                Paragraph("—", styles["body"]),
                Paragraph("unavailable", styles["muted"]),
            ])
        else:
            rate_str = f"{r['rate']:.6f}" if r.get("rate") else "—"
            rows.append([
                Paragraph(f"{r['base']}/{r['target']}", styles["body"]),
                Paragraph(rate_str, styles["body"]),
                Paragraph(r.get("date", "—"), styles["muted"]),
            ])

    col_widths = [40 * mm, 50 * mm, 40 * mm]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  BRAND_PRIMARY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BRAND_LIGHT, colors.white]),
        ("GRID",       (0, 0), (-1, -1),  0.5, colors.HexColor("#CCCCCC")),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _build_news_table(news: list[dict], styles) -> Optional[Table]:
    """Build a news items table from insight data."""
    if not news:
        return None

    header_style = styles["table_header"]
    rows = [
        [
            Paragraph("Headline", header_style),
            Paragraph("Source", header_style),
        ]
    ]
    for n in (news[:10]):  # cap at 10
        rows.append([
            Paragraph(n.get("title", "—"), styles["body"]),
            Paragraph(n.get("source", n.get("published", "")), styles["muted"]),
        ])

    col_widths = [100 * mm, 30 * mm]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  BRAND_ACCENT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BRAND_LIGHT, colors.white]),
        ("GRID",       (0, 0), (-1, -1),  0.5, colors.HexColor("#CCCCCC")),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _build_sources_list(sources: list[dict], styles) -> list:
    """Build a list of source documents."""
    items = []
    if not sources:
        return items
    items.append(Paragraph("Sources", styles["section"]))
    for s in sources:
        name = s.get("name", "Unknown document")
        items.append(Paragraph(f"• {name}", styles["body"]))
    return items


def generate_insight_pdf(reply: str, data: Optional[Any], tool_used: Optional[str]) -> bytes:
    """
    Render a chat response (reply text + structured data) as a PDF.

    Args:
        reply:       The LLM's natural-language reply/summary.
        data:        Structured tool data (dict with type: insight|dashboard|news|rag).
        tool_used:   Name of the tool that produced the data.

    Returns:
        PDF as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="AI Market Studio — FX Insight Report",
        author="AI Market Studio",
    )

    styles = _styles()
    story = []

    meta = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "tool_used": tool_used or "N/A",
    }

    _build_header(story, meta, styles)

    # Reply / summary section
    story.append(Paragraph("Summary", styles["section"]))
    story.append(Paragraph(reply or "No summary available.", styles["body"]))
    story.append(Spacer(1, 4 * mm))

    # Structured data sections
    if data and isinstance(data, dict):
        dtype = data.get("type", "")

        if dtype == "insight":
            rates = data.get("rates", [])
            if rates:
                story.append(Paragraph("FX Rates", styles["section"]))
                t = _build_rates_table(rates, styles)
                if t:
                    story.append(t)
                story.append(Spacer(1, 4 * mm))

            news = data.get("news", [])
            if news:
                story.append(Paragraph("Market News", styles["section"]))
                t = _build_news_table(news, styles)
                if t:
                    story.append(t)
                story.append(Spacer(1, 4 * mm))

        elif dtype == "dashboard":
            story.append(Paragraph("Dashboard Data", styles["section"]))
            panel_type = data.get("panel_type", "N/A")
            base = data.get("base", "N/A")
            targets = ", ".join(data.get("targets", []))
            start = data.get("start_date", "—")
            end = data.get("end_date", "—")
            story.append(Paragraph(f"<b>Type:</b> {panel_type}", styles["body"]))
            story.append(Paragraph(f"<b>Base:</b> {base}", styles["body"]))
            story.append(Paragraph(f"<b>Targets:</b> {targets}", styles["body"]))
            story.append(Paragraph(f"<b>Period:</b> {start} → {end}", styles["body"]))

            series = data.get("series", [])
            if series:
                story.append(Spacer(1, 4 * mm))
                rows = [[Paragraph("Date", styles["table_header"])] + [
                    Paragraph(t, styles["table_header"])
                    for t in data.get("targets", [])
                ]]
                for row in series[:30]:  # cap at 30 rows
                    rows.append([
                        Paragraph(row.get("date", ""), styles["muted"])
                    ] + [
                        Paragraph(str(row.get("rates", {}).get(t, "—")), styles["body"])
                        for t in data.get("targets", [])
                    ])
                if len(rows) > 1:
                    col_count = len(data.get("targets", [])) + 1
                    col_widths = [35 * mm] + [(A4[0] - 40 * mm) / (col_count - 1)] * (col_count - 1)
                    t = Table(rows, colWidths=col_widths, repeatRows=1)
                    t.setStyle(TableStyle([
                        ("BACKGROUND",  (0, 0), (-1, 0),  BRAND_PRIMARY),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BRAND_LIGHT, colors.white]),
                        ("GRID",       (0, 0), (-1, -1),  0.5, colors.HexColor("#CCCCCC")),
                        ("TOPPADDING",  (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
                    ]))
                    story.append(t)

        elif dtype == "news":
            items = data.get("items", [])
            if items:
                story.append(Paragraph("News Headlines", styles["section"]))
                t = _build_news_table(items, styles)
                if t:
                    story.append(t)

        elif dtype == "rag":
            sources = data.get("sources", [])
            if sources:
                story.extend(_build_sources_list(sources, styles))

    # Footer rule
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_LIGHT))
    story.append(Paragraph(
        "This report was generated by AI Market Studio. Data is indicative and not financial advice.",
        styles["muted"]
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
