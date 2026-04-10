"""
PDF Skill — AI Market Studio FX Insight Reports

A structured PDF generation skill following reportlab best practices:
- SimpleDocTemplate + Platypus for layout
- Paragraph for text, Table for tabular data
- Consistent brand styling (navy/teal palette)
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
    KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# ─── Brand palette ───────────────────────────────────────────────────────────
BRAND_PRIMARY = colors.HexColor("#1A3A5C")   # deep navy — headers, title
BRAND_ACCENT  = colors.HexColor("#2E7D9B")   # teal — section accents, news table header
BRAND_LIGHT   = colors.HexColor("#F0F4F8")   # light gray-blue — table row bg
BRAND_FOOTER  = colors.HexColor("#E8EDF2")   # footer bg
TEXT_BODY     = colors.HexColor("#222222")
TEXT_MUTED    = colors.HexColor("#666666")
WHITE         = colors.white

# ─── Style definitions (following PDF skill patterns) ───────────────────────
def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["Normal"]
    base.fontName = "Helvetica"
    base.textColor = TEXT_BODY

    return {
        "title": ParagraphStyle(
            "SkillTitle",
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=BRAND_PRIMARY,
            spaceAfter=4,
            leading=28,
        ),
        "subtitle": ParagraphStyle(
            "SkillSubtitle",
            fontName="Helvetica",
            fontSize=11,
            textColor=TEXT_MUTED,
            spaceAfter=2,
        ),
        "section": ParagraphStyle(
            "SkillSection",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=BRAND_PRIMARY,
            spaceBefore=12,
            spaceAfter=5,
            leading=17,
        ),
        "body": ParagraphStyle(
            "SkillBody",
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            spaceAfter=5,
        ),
        "muted": ParagraphStyle(
            "SkillMuted",
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor=TEXT_MUTED,
            spaceAfter=3,
        ),
        "table_header": ParagraphStyle(
            "SkillTableHeader",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=WHITE,
        ),
        "footer": ParagraphStyle(
            "SkillFooter",
            fontName="Helvetica-Oblique",
            fontSize=8,
            textColor=TEXT_MUTED,
            alignment=TA_CENTER,
        ),
    }


# ─── Table builder helpers (following PDF skill patterns) ──────────────────
def _base_table_style(header_bg: colors.Color) -> list:
    """Base style for data tables — alternating rows + clean borders."""
    return [
        ("BACKGROUND",  (0, 0), (-1, 0),  header_bg),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BRAND_LIGHT, WHITE]),
        ("GRID",       (0, 0), (-1, -1),  0.5, colors.HexColor("#CCCCCC")),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ]


def _rates_table(rates: list[dict], styles: dict) -> Optional[Table]:
    if not rates:
        return None
    header = styles["table_header"]
    rows = [
        [Paragraph("Pair", header), Paragraph("Rate", header), Paragraph("Date", header)],
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
    table = Table(rows, colWidths=[40*mm, 50*mm, 40*mm], repeatRows=1)
    table.setStyle(TableStyle(_base_table_style(BRAND_PRIMARY)))
    return table


def _news_table(news: list[dict], styles: dict) -> Optional[Table]:
    if not news:
        return None
    header = styles["table_header"]
    rows = [[Paragraph("Headline", header), Paragraph("Source", header)]]
    for n in news[:10]:
        rows.append([
            Paragraph(n.get("title", "—"), Paragraph(n.get("source", n.get("published", "")[:20]), styles["muted"]),
        ])
    table = Table(rows, colWidths=[100*mm, 30*mm], repeatRows=1)
    table.setStyle(TableStyle(_base_table_style(BRAND_ACCENT)))
    return table


def _sources_block(sources: list[dict], styles: dict) -> list:
    """Block of source document items."""
    items = []
    if not sources:
        return items
    items.append(Paragraph("Sources", styles["section"]))
    for s in sources:
        name = s.get("name", "Unknown document")
        items.append(Paragraph(f"\u2022 {name}", styles["body"]))
    return items


def _dashboard_table(data: dict, styles: dict) -> Optional[Table]:
    """Time-series table for dashboard data."""
    series = data.get("series", [])
    targets = data.get("targets", [])
    if not series or not targets:
        return None
    header = styles["table_header"]
    col_count = len(targets) + 1
    col_widths = [35*mm] + [(A4[0] - 40*mm) / (col_count - 1)] * (col_count - 1)
    rows = [[Paragraph("Date", header)] + [Paragraph(t, header) for t in targets]]
    for row in series[:30]:
        rows.append(
            [Paragraph(row.get("date", ""), styles["muted"])]
            + [Paragraph(str(row.get("rates", {}).get(t, "—")), styles["body"]) for t in targets]
        )
    if len(rows) < 2:
        return None
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle(_base_table_style(BRAND_PRIMARY)))
    return table


# ─── Skill interface ─────────────────────────────────────────────────────────
def generate(payload: dict) -> bytes:
    """
    Generate a PDF report from structured FX insight data.

    Args:
        payload: {
            "report_type": "fx-insight" | "fx-dashboard" | "fx-news" | "fx-rag",
            "reply": str,           # LLM's natural-language summary
            "data": dict,           # structured tool data (type, rates, news, etc.)
            "tool_used": str,       # tool name that produced the data
            "generated_at": str,    # ISO timestamp
        }

    Returns:
        PDF document as bytes.
    """
    report_type = payload.get("report_type", "fx-insight")
    reply       = payload.get("reply", "")
    data        = payload.get("data", {})
    tool_used   = payload.get("tool_used", "N/A")
    generated_at = payload.get("generated_at") or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm,
        title="AI Market Studio — FX Insight Report",
        author="AI Market Studio",
    )

    styles = _styles()
    story  = []

    # ── Header ──────────────────────────────────────────────────────────────
    story.append(Paragraph("AI Market Studio", styles["title"]))
    story.append(Paragraph("FX Market Intelligence Report", styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=BRAND_ACCENT, spaceAfter=6))
    story.append(Paragraph(
        f"Generated: {generated_at}  |  Tool: {tool_used}  |  Type: {report_type}",
        styles["muted"]
    ))
    story.append(Spacer(1, 6*mm))

    # ── Summary ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Summary", styles["section"]))
    story.append(Paragraph(reply or "No summary available.", styles["body"]))
    story.append(Spacer(1, 4*mm))

    # ── Structured data sections ───────────────────────────────────────────
    dtype = data.get("type", "") if isinstance(data, dict) else ""

    if dtype in ("insight", "") and data.get("rates"):
        items = [_rates_table(data["rates"], styles)]
        if data.get("news"):
            items.append(_news_table(data["news"], styles))
        if items:
            story.append(KeepTogether([Paragraph("FX Rates", styles["section"])] + [i for i in items if i]))

    if dtype == "dashboard":
        panel_type = data.get("panel_type", "N/A")
        base = data.get("base", "N/A")
        targets = ", ".join(data.get("targets", []))
        start = data.get("start_date", "—")
        end = data.get("end_date", "—")
        story.append(Paragraph("Dashboard Data", styles["section"]))
        story.append(Paragraph(f"<b>Type:</b> {panel_type}", styles["body"]))
        story.append(Paragraph(f"<b>Base:</b> {base}", styles["body"]))
        story.append(Paragraph(f"<b>Targets:</b> {targets}", styles["body"]))
        story.append(Paragraph(f"<b>Period:</b> {start} \u2192 {end}", styles["body"]))
        t = _dashboard_table(data, styles)
        if t:
            story.append(Spacer(1, 3*mm))
            story.append(t)

    if dtype == "news" and data.get("items"):
        t = _news_table(data["items"], styles)
        if t:
            story.append(Paragraph("News Headlines", styles["section"]))
            story.append(t)

    if dtype == "rag" and data.get("sources"):
        story.extend(_sources_block(data["sources"], styles))

    # ── Footer ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_LIGHT))
    story.append(Paragraph(
        "This report was generated by AI Market Studio. Data is indicative and not financial advice.",
        styles["footer"]
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
