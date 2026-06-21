"""
PDF exporter for AI Market Studio chat responses.
Renders structured FX market insights as a formatted PDF document.
"""
import io
from datetime import UTC, datetime
from typing import Any, Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


BRAND_PRIMARY = colors.HexColor("#1A3A5C")
BRAND_ACCENT = colors.HexColor("#2E7D9B")
BRAND_LIGHT = colors.HexColor("#F0F4F8")
TEXT_BODY = colors.HexColor("#222222")
TEXT_MUTED = colors.HexColor("#666666")
PLACEHOLDER = "N/A"


def _styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    base = styles["Normal"]
    base.textColor = TEXT_BODY
    base.fontName = "Helvetica"

    return {
        "title": ParagraphStyle(
            "DocTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=BRAND_PRIMARY,
            spaceAfter=4,
            leading=28,
        ),
        "subtitle": ParagraphStyle(
            "DocSubtitle",
            parent=base,
            fontName="Helvetica",
            fontSize=11,
            textColor=TEXT_MUTED,
            spaceAfter=2,
        ),
        "section": ParagraphStyle(
            "SectionHead",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=BRAND_PRIMARY,
            spaceBefore=14,
            spaceAfter=6,
            leading=18,
        ),
        "body": ParagraphStyle(
            "DocBody",
            parent=base,
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            spaceAfter=6,
        ),
        "muted": ParagraphStyle(
            "Muted",
            parent=base,
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor=TEXT_MUTED,
            spaceAfter=4,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.white,
        ),
    }


def _text(value: Any, default: str = PLACEHOLDER) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else default
    return str(value)


def _inline(value: Any, default: str = PLACEHOLDER) -> str:
    return escape(_text(value, default))


def _paragraph(value: Any, style: ParagraphStyle, default: str = PLACEHOLDER) -> Paragraph:
    html = _inline(value, default).replace("\n", "<br/>")
    return Paragraph(html, style)


def _label_value(label: str, value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(f"<b>{escape(label)}:</b> {_inline(value)}", style)


def _format_list(value: Any) -> str:
    if value is None:
        return PLACEHOLDER
    if isinstance(value, list):
        return ", ".join(_text(item) for item in value) if value else PLACEHOLDER
    return _text(value)


def _format_metric(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return _text(value)


def _table_style(header_bg: colors.Color) -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BRAND_LIGHT, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
    )


def _build_header(story: list, meta: dict, styles: dict[str, ParagraphStyle]) -> None:
    story.append(_paragraph("AI Market Studio", styles["title"]))
    story.append(_paragraph("FX Market Intelligence Report", styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=BRAND_ACCENT, spaceAfter=8))
    story.append(
        _paragraph(
            f"Generated: {meta['generated_at']} | Tool: {meta.get('tool_used', PLACEHOLDER)}",
            styles["muted"],
        )
    )
    story.append(Spacer(1, 6 * mm))


def _build_rates_table(rates: list[dict], styles: dict[str, ParagraphStyle]) -> Optional[Table]:
    if not rates:
        return None

    header = styles["table_header"]
    rows = [[_paragraph("Pair", header), _paragraph("Rate", header), _paragraph("Date", header)]]
    for rate in rates:
        pair = f"{_text(rate.get('base'))}/{_text(rate.get('target'))}"
        if rate.get("error"):
            rows.append(
                [
                    _paragraph(pair, styles["body"]),
                    _paragraph(PLACEHOLDER, styles["body"]),
                    _paragraph("unavailable", styles["muted"]),
                ]
            )
            continue

        raw_rate = rate.get("rate")
        rate_text = f"{raw_rate:.6f}" if isinstance(raw_rate, float) else _text(raw_rate)
        rows.append(
            [
                _paragraph(pair, styles["body"]),
                _paragraph(rate_text, styles["body"]),
                _paragraph(rate.get("date"), styles["muted"]),
            ]
        )

    table = Table(rows, colWidths=[40 * mm, 50 * mm, 40 * mm], repeatRows=1)
    table.setStyle(_table_style(BRAND_PRIMARY))
    return table


def _build_news_table(news: list[dict], styles: dict[str, ParagraphStyle]) -> Optional[Table]:
    if not news:
        return None

    header = styles["table_header"]
    rows = [[_paragraph("Headline", header), _paragraph("Source", header)]]
    for item in news[:10]:
        rows.append(
            [
                _paragraph(item.get("title"), styles["body"]),
                _paragraph(item.get("source", item.get("published", "")), styles["muted"]),
            ]
        )

    table = Table(rows, colWidths=[100 * mm, 30 * mm], repeatRows=1)
    table.setStyle(_table_style(BRAND_ACCENT))
    return table


def _build_sources_list(sources: list[dict], styles: dict[str, ParagraphStyle]) -> list:
    if not sources:
        return []

    items = [_paragraph("Sources", styles["section"])]
    for source in sources:
        items.append(_paragraph(f"- {_text(source.get('name'), 'Unknown document')}", styles["body"]))
    return items


def _append_table(story: list, heading: str, table: Optional[Table], styles: dict[str, ParagraphStyle]) -> None:
    if not table:
        return
    story.append(_paragraph(heading, styles["section"]))
    story.append(table)
    story.append(Spacer(1, 4 * mm))


def _append_source_grounding(story: list, data: dict, styles: dict[str, ParagraphStyle]) -> None:
    source_grounding = data.get("source_grounding")
    if not isinstance(source_grounding, dict):
        return

    story.append(_paragraph("Source Grounding", styles["section"]))
    for key in (
        "requested_sources",
        "available_sources",
        "synthetic_sources",
        "missing_required_sources",
        "missing_optional_sources",
    ):
        if key in source_grounding:
            story.append(_label_value(key, _format_list(source_grounding.get(key)), styles["body"]))


def _append_data_gaps(story: list, data: dict, styles: dict[str, ParagraphStyle]) -> None:
    gaps = data.get("data_gaps")
    if not gaps:
        return

    story.append(_paragraph("Data Gaps", styles["section"]))
    if isinstance(gaps, list):
        for gap in gaps:
            story.append(_paragraph(f"- {_text(gap)}", styles["body"]))
    else:
        story.append(_paragraph(gaps, styles["body"]))


def _append_carry_metrics(story: list, data: dict, styles: dict[str, ParagraphStyle]) -> None:
    metrics = data.get("carry_metrics")
    if not isinstance(metrics, dict):
        return

    story.append(_paragraph("Carry Metrics", styles["section"]))
    for key, value in metrics.items():
        story.append(_label_value(key, _format_metric(value), styles["body"]))


def _append_dashboard(story: list, data: dict, styles: dict[str, ParagraphStyle]) -> None:
    story.append(_paragraph("Dashboard Data", styles["section"]))
    story.append(_label_value("Type", data.get("panel_type"), styles["body"]))
    story.append(_label_value("Base", data.get("base"), styles["body"]))
    story.append(_label_value("Targets", _format_list(data.get("targets", [])), styles["body"]))
    story.append(
        _label_value(
            "Period",
            f"{_text(data.get('start_date'))} -> {_text(data.get('end_date'))}",
            styles["body"],
        )
    )

    series = data.get("series", [])
    targets = data.get("targets", [])
    if not series or not targets:
        return

    rows = [[_paragraph("Date", styles["table_header"])] + [_paragraph(target, styles["table_header"]) for target in targets]]
    for row in series[:30]:
        rows.append(
            [_paragraph(row.get("date", ""), styles["muted"])]
            + [_paragraph(row.get("rates", {}).get(target), styles["body"]) for target in targets]
        )

    col_count = len(targets) + 1
    col_widths = [35 * mm] + [(A4[0] - 40 * mm) / (col_count - 1)] * (col_count - 1)
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(_table_style(BRAND_PRIMARY))
    story.append(Spacer(1, 4 * mm))
    story.append(table)


def _append_market_context(story: list, data: dict, styles: dict[str, ParagraphStyle]) -> None:
    workflow_context = data if data.get("type") == "market_context" else data.get("context", {})
    context = workflow_context.get("context", {}) if isinstance(workflow_context, dict) else {}

    _append_table(story, "Spot Rates", _build_rates_table(context.get("rates", []), styles), styles)

    history = context.get("historical_rates", [])
    if history:
        rows = [
            [
                _paragraph("Pair", styles["table_header"]),
                _paragraph("Start", styles["table_header"]),
                _paragraph("End", styles["table_header"]),
                _paragraph("Observations", styles["table_header"]),
            ]
        ]
        for item in history:
            rows.append(
                [
                    _paragraph(item.get("pair"), styles["body"]),
                    _paragraph(item.get("start_date"), styles["muted"]),
                    _paragraph(item.get("end_date"), styles["muted"]),
                    _paragraph(len(item.get("series", [])), styles["body"]),
                ]
            )
        table = Table(rows, colWidths=[35 * mm, 35 * mm, 35 * mm, 35 * mm], repeatRows=1)
        table.setStyle(_table_style(BRAND_PRIMARY))
        _append_table(story, "Historical Rates", table, styles)

    _append_table(story, "Market News", _build_news_table(context.get("news", []), styles), styles)

    research = context.get("research", {})
    sources = []
    if isinstance(research, dict):
        sources = research.get("sources", []) or research.get("results", [])
    if sources:
        story.extend(_build_sources_list(sources, styles))

    _append_source_grounding(story, data, styles)
    _append_data_gaps(story, data, styles)
    _append_carry_metrics(story, data, styles)


def generate_insight_pdf(reply: str, data: Optional[Any], tool_used: Optional[str]) -> bytes:
    """
    Render a chat response (reply text + structured data) as a PDF.

    Args:
        reply: The LLM natural-language reply or summary.
        data: Structured tool data.
        tool_used: Name of the tool that produced the data.

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
        title="AI Market Studio - FX Insight Report",
        author="AI Market Studio",
    )

    styles = _styles()
    story: list = []
    meta = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "tool_used": tool_used or PLACEHOLDER,
    }

    _build_header(story, meta, styles)
    story.append(_paragraph("Summary", styles["section"]))
    story.append(_paragraph(reply or "No summary available.", styles["body"]))
    story.append(Spacer(1, 4 * mm))

    if data and isinstance(data, dict):
        dtype = data.get("type", "")
        if dtype == "insight":
            _append_table(story, "FX Rates", _build_rates_table(data.get("rates", []), styles), styles)
            _append_table(story, "Market News", _build_news_table(data.get("news", []), styles), styles)
        elif dtype == "dashboard":
            _append_dashboard(story, data, styles)
        elif dtype == "news":
            _append_table(story, "News Headlines", _build_news_table(data.get("items", []), styles), styles)
        elif dtype == "rag":
            story.extend(_build_sources_list(data.get("sources", []), styles))
        elif dtype in ("market_context", "market_briefing"):
            _append_market_context(story, data, styles)
        elif {"base", "target", "rate"}.issubset(data):
            rate_row = {
                "base": data.get("base"),
                "target": data.get("target"),
                "rate": data.get("rate"),
                "date": data.get("date"),
            }
            _append_table(story, "FX Rates", _build_rates_table([rate_row], styles), styles)

    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_LIGHT))
    story.append(
        _paragraph(
            "This report was generated by AI Market Studio. Data is indicative and not financial advice.",
            styles["muted"],
        )
    )

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
