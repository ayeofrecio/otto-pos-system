"""
reports/pdf/series_pdf.py

ReportLab builder for the Series Sales Report.
Takes the context dict produced by services/series_report.py and returns
raw PDF bytes.  Zero system dependencies — pure Python.

Layout (top → bottom):
  1. Terminal / store header block
  2. Report meta (business date, session info, beg/end SI)
  3. Detail table  ← repeats header on every page automatically
  4. Summary box   (right-aligned, gross / VAT / net / qty)
  5. Signature lines

Usage:
    from reports.services.series_report import build_series_report
    from reports.pdf.series_pdf import build_series_pdf

    context  = build_series_report(session_id)
    pdf_bytes = build_series_pdf(context, paper="a4")
"""

import io
from datetime import datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, LETTER, LEGAL, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfgen import canvas as rl_canvas


# ---------------------------------------------------------------------------
# Constants — colours
# ---------------------------------------------------------------------------
COLOR_HEADER_BG   = colors.HexColor("#1a1a2e")   # dark navy — table header
COLOR_HEADER_TEXT = colors.white
COLOR_ROW_ALT     = colors.HexColor("#f5f5f5")   # alternating row tint
COLOR_GRID        = colors.HexColor("#cccccc")
COLOR_TOTAL_BG    = colors.HexColor("#e0e0e0")
COLOR_SUMMARY_BG  = colors.HexColor("#f0f0f0")
COLOR_RULE        = colors.HexColor("#333333")


# ---------------------------------------------------------------------------
# Paper size map
# ---------------------------------------------------------------------------
PAPER_MAP = {
    "a4":     landscape(A4),
    "letter": landscape(LETTER),
    "long":   landscape(LEGAL),   # "long" bond / legal
}
DEFAULT_PAPER = "a4"

# Margins
MARGIN_TOP    = 5 * mm
MARGIN_BOTTOM = 16 * mm   # slightly more for page number
MARGIN_LEFT   = 12 * mm
MARGIN_RIGHT  = 12 * mm


# ---------------------------------------------------------------------------
# Column widths (pt) — tuned for landscape A4 usable width ≈ 267mm = 757pt
#
#   SI No.    55
#   Date      55
#   Item No.  72
#   Item Name 130   ← wraps
#   Color      55
#   Size       35
#   Qty        42   ← right-aligned
#   Amount     65   ← right-aligned
#   VAT        55   ← right-aligned
#   Payment    90   ← wraps
#   ─────────────
#   Total     654pt   comfortable fit
# ---------------------------------------------------------------------------
# COL_WIDTHS = [55, 55, 72, 130, 55, 35, 42, 65, 55, 90]
COL_WIDTHS = [55, 72, 130, 55, 35, 42, 65, 55, 90]

# Column indices (0-based)
COL_QTY    = 6
COL_AMOUNT = 7
COL_VAT    = 8


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
_base_styles = getSampleStyleSheet()

def _make_styles():
    return {
        "header_store": ParagraphStyle(
            "header_store",
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            alignment=TA_CENTER,
        ),
        "header_line": ParagraphStyle(
            "header_line",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            alignment=TA_CENTER,
        ),
        "report_title": ParagraphStyle(
            "report_title",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "meta_label": ParagraphStyle(
            "meta_label",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            alignment=TA_LEFT,
        ),
        "meta_label_right": ParagraphStyle(
            "meta_label_right",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            alignment=TA_RIGHT,
        ),
        "table_header": ParagraphStyle(
            "table_header",
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            alignment=TA_CENTER,
            textColor=colors.white,
        ),
        "cell_center": ParagraphStyle(
            "cell_center",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            alignment=TA_CENTER,
        ),
        "cell_left": ParagraphStyle(
            "cell_left",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            alignment=TA_LEFT,
        ),
        "cell_right": ParagraphStyle(
            "cell_right",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            alignment=TA_RIGHT,
        ),
        "cell_wrap": ParagraphStyle(
            "cell_wrap",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            alignment=TA_LEFT,
            wordWrap="LTR",
        ),
        "total_label": ParagraphStyle(
            "total_label",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            alignment=TA_RIGHT,
        ),
        "total_value": ParagraphStyle(
            "total_value",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            alignment=TA_RIGHT,
        ),
        "summary_label": ParagraphStyle(
            "summary_label",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            alignment=TA_RIGHT,
        ),
        "summary_value": ParagraphStyle(
            "summary_value",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            alignment=TA_RIGHT,
        ),
        "sig_label": ParagraphStyle(
            "sig_label",
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            alignment=TA_CENTER,
        ),
    }


# ---------------------------------------------------------------------------
# Numbered Canvas — adds page number + print timestamp to every page
# ---------------------------------------------------------------------------
class _NumberedCanvas(rl_canvas.Canvas):
    """Draws page N of M footer after the document is fully built."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_footer(total)
            rl_canvas.Canvas.showPage(self)
        rl_canvas.Canvas.save(self)

    def _draw_page_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 7)
        self.setFillColor(colors.HexColor("#555555"))

        # Left — print timestamp
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.drawString(MARGIN_LEFT, 8 * mm, f"Printed: {ts}")

        # Right — page N of M
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(
            self._pagesize[0] - MARGIN_RIGHT, 8 * mm, page_text
        )
        self.restoreState()


# ---------------------------------------------------------------------------
# Internal builder helpers
# ---------------------------------------------------------------------------

def _fmt_decimal(value, decimals=2) -> str:
    """Format a Decimal or float to a string with comma thousands separator."""
    try:
        d = Decimal(str(value))
        if decimals == 0:
            return f"{int(d):,}"
        return f"{d:,.{decimals}f}"
    except Exception:
        return str(value)


def _build_header_block(ctx: dict, styles: dict) -> list:
    """
    Returns a list of Platypus flowables for the terminal / store header block.
    """
    flowables = []

    header_lines = ctx.get("header_lines", [])

    if header_lines:
        # First line = store name (bold, larger)
        flowables.append(Paragraph(header_lines[0], styles["header_store"]))
        for line in header_lines[1:]:
            flowables.append(Paragraph(line, styles["header_line"]))
    else:
        # Fallback if no receipt headers configured
        flowables.append(
            Paragraph(
                f"Store {ctx['store_id']} — Terminal {ctx['terminal_id']}",
                styles["header_store"],
            )
        )

    flowables.append(Spacer(1, 4))
    flowables.append(Paragraph("SERIES SALES REPORT", styles["report_title"]))
    flowables.append(
        HRFlowable(width="100%", thickness=1.5, color=COLOR_RULE, spaceAfter=4)
    )
    return flowables


def _build_meta_block(ctx: dict, styles: dict, page_width: float) -> list:
    """
    Returns a two-column meta table:
      Left  — business date, store, session info, opened/closed by
      Right — beg SI, end SI, transaction count, VAT rate
    """
    biz_date = ctx["business_date"]
    date_str  = biz_date.strftime("%B %d, %Y") if hasattr(biz_date, "strftime") else str(biz_date)

    session   = ctx["session"]
    vat_pct   = int(ctx["vat_rate"] * 100)

    left_lines = [
        f"<b>Business Date:</b> {date_str}",
        f"<b>Store ID:</b> {ctx['store_id']}    <b>Terminal:</b> {ctx['terminal_id']}",
        f"<b>Session:</b> #{session.id}  |  <b>Status:</b> {session.get_status_display()}",
        f"<b>Opened by:</b> {ctx['opened_by']}"
        + (f"  /  <b>Closed by:</b> {ctx['closed_by']}" if session.closed_by else ""),
    ]

    right_lines = [
        f"<b>Beg. SI No.:</b>  {ctx['beg_si']}",
        f"<b>End. SI No.:</b>  {ctx['end_si']}",
        f"<b>Total Transactions:</b>  {ctx['transaction_count']}",
        f"<b>VAT Rate:</b>  {vat_pct}%",
    ]

    # Build as a 2-cell table so left/right align naturally
    usable = page_width - MARGIN_LEFT - MARGIN_RIGHT
    half   = usable / 2

    left_para  = [Paragraph(line, styles["meta_label"])       for line in left_lines]
    right_para = [Paragraph(line, styles["meta_label_right"]) for line in right_lines]

    meta_table = Table(
        [[left_para, right_para]],
        colWidths=[half, half],
    )
    meta_table.setStyle(TableStyle([
        ("VALIGN",  (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 0),
    ]))

    return [meta_table, Spacer(1, 6)]


def _build_detail_table(ctx: dict, styles: dict) -> list:
    """
    Returns the main detail table as a list containing one Table flowable.
    The table header (row 0) repeats on every page via repeatRows=1.
    """

    # -- Header row --
    col_labels = [
        "SI No.", "Item No.", "Item Name",
        # "SI No.", "Date", "Item No.", "Item Name",
        "Color", "Size", "Qty\nSold", "Amount", "VAT", "Mode of\nPayment",
    ]
    header_row = [
        Paragraph(label, styles["table_header"]) for label in col_labels
    ]

    # -- Data rows --
    rows = ctx.get("rows", [])
    table_data = [header_row]

    for row in rows:
        # date_str = (
        #     row["date"].strftime("%m/%d/%Y")
        #     if hasattr(row["date"], "strftime")
        #     else str(row["date"])
        # )
        table_data.append([
            Paragraph(row["si_no"],        styles["cell_center"]),
            # Paragraph(date_str,            styles["cell_center"]),
            Paragraph(row["item_no"],      styles["cell_left"]),
            Paragraph(row["item_name"],    styles["cell_wrap"]),      # wraps
            Paragraph(row["color"],        styles["cell_center"]),
            Paragraph(row["size"],         styles["cell_center"]),
            Paragraph(_fmt_decimal(row["qty"], 0),    styles["cell_right"]),
            Paragraph(_fmt_decimal(row["amount"]),    styles["cell_right"]),
            Paragraph(_fmt_decimal(row["vat"]),       styles["cell_right"]),
            Paragraph(row["payment_mode"], styles["cell_wrap"]),      # wraps
        ])

    # -- Totals row --
    table_data.append([
        Paragraph("TOTALS", styles["total_label"]),  # col 0
        "", "", "", "", "",                           # cols 1-5 (merged via span)
        Paragraph(_fmt_decimal(ctx["total_qty"], 0),    styles["total_value"]),
        Paragraph(_fmt_decimal(ctx["total_amount"]),    styles["total_value"]),
        Paragraph(_fmt_decimal(ctx["total_vat"]),       styles["total_value"]),
        "",                                           # payment col
    ])

    total_row_idx = len(table_data) - 1

    # -- Table style --
    style = TableStyle([
        # Header row — dark navy background
        ("BACKGROUND",    (0, 0),  (-1, 0),               COLOR_HEADER_BG),
        ("TEXTCOLOR",     (0, 0),  (-1, 0),               COLOR_HEADER_TEXT),
        ("FONTNAME",      (0, 0),  (-1, 0),               "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0),  (-1, 0),               7),
        ("ALIGN",         (0, 0),  (-1, 0),               "CENTER"),
        ("VALIGN",        (0, 0),  (-1, 0),               "MIDDLE"),
        ("MINROWHEIGHT",  (0, 0),  (-1, 0),               14),

        # Data rows
        ("FONTNAME",      (0, 1),  (-1, total_row_idx - 1), "Helvetica"),
        ("FONTSIZE",      (0, 1),  (-1, total_row_idx - 1), 7),
        ("VALIGN",        (0, 1),  (-1, -1),              "TOP"),
        ("TOPPADDING",    (0, 1),  (-1, -1),              2),
        ("BOTTOMPADDING", (0, 1),  (-1, -1),              2),
        ("LEFTPADDING",   (0, 0),  (-1, -1),              3),
        ("RIGHTPADDING",  (0, 0),  (-1, -1),              3),

        # Alternating row background
        ("ROWBACKGROUNDS", (0, 1), (-1, total_row_idx - 1),
         [colors.white, COLOR_ROW_ALT]),

        # Grid
        ("GRID",          (0, 0),  (-1, -1),              0.5, COLOR_GRID),

        # Totals row
        ("BACKGROUND",    (0, total_row_idx), (-1, total_row_idx), COLOR_TOTAL_BG),
        ("FONTNAME",      (0, total_row_idx), (-1, total_row_idx), "Helvetica-Bold"),
        ("FONTSIZE",      (0, total_row_idx), (-1, total_row_idx), 7.5),
        ("LINEABOVE",     (0, total_row_idx), (-1, total_row_idx), 1, COLOR_RULE),

        # Span "TOTALS" label across cols 0-5
        ("SPAN",          (0, total_row_idx), (5, total_row_idx)),
        ("ALIGN",         (0, total_row_idx), (5, total_row_idx), "RIGHT"),
    ])

    table = Table(
        table_data,
        colWidths=COL_WIDTHS,
        repeatRows=1,          # repeat header on every page
        hAlign="LEFT",
    )
    table.setStyle(style)

    return [table]


def _build_summary_block(ctx: dict, styles: dict, page_width: float) -> list:
    """
    Right-aligned summary table: Gross Sales / VAT / Net of VAT / Total Qty.
    """
    # Net of VAT = total_amount - total_vat
    net_of_vat = ctx["total_amount"] - ctx["total_vat"]

    summary_data = [
        ["Gross Sales",  _fmt_decimal(ctx["total_amount"])],
        ["Total VAT",    _fmt_decimal(ctx["total_vat"])],
        ["Net of VAT",   _fmt_decimal(net_of_vat)],
        ["Total Qty Sold", _fmt_decimal(ctx["total_qty"], 0)],
    ]

    # Build as Paragraph pairs for consistent font control
    summary_rows = [
        [
            Paragraph(lbl, styles["summary_label"]),
            Paragraph(val, styles["summary_value"]),
        ]
        for lbl, val in summary_data
    ]

    summary_table = Table(
        summary_rows,
        colWidths=[100, 80],
        hAlign="RIGHT",
    )
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (0, -1), COLOR_SUMMARY_BG),
        ("GRID",        (0, 0), (-1, -1), 0.5, COLOR_GRID),
        ("TOPPADDING",  (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE",   (0, 0), (-1, 0), 1.5, COLOR_RULE),
    ]))

    return [Spacer(1, 8), summary_table]


def _build_signature_block(styles: dict, page_width: float) -> list:
    """
    Three evenly spaced signature lines: Prepared by / Checked by / Approved by.
    """
    usable    = page_width - MARGIN_LEFT - MARGIN_RIGHT
    col_width = usable / 3

    sig_data = [[
        Paragraph("_" * 28, styles["sig_label"]),
        Paragraph("_" * 28, styles["sig_label"]),
        Paragraph("_" * 28, styles["sig_label"]),
    ], [
        Paragraph("Prepared by",  styles["sig_label"]),
        Paragraph("Checked by",   styles["sig_label"]),
        Paragraph("Approved by",  styles["sig_label"]),
    ]]

    sig_table = Table(sig_data, colWidths=[col_width, col_width, col_width])
    sig_table.setStyle(TableStyle([
        ("ALIGN",   (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",  (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    return [Spacer(1, 24), sig_table]


def _build_no_data_block(styles: dict) -> list:
    """Shown when the session has no non-void transactions."""
    return [
        Spacer(1, 20),
        Paragraph(
            "No transactions found for this session.",
            ParagraphStyle(
                "no_data",
                fontName="Helvetica-Oblique",
                fontSize=9,
                alignment=TA_CENTER,
                textColor=colors.grey,
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_series_pdf(ctx: dict, paper: str = DEFAULT_PAPER) -> bytes:
    """
    Build the Series Sales Report PDF from the context dict produced by
    services/series_report.py.

    Args:
        ctx:   Context dict from build_series_report().
        paper: One of "a4", "letter", "long".  Defaults to "a4".

    Returns:
        Raw PDF bytes ready to stream via HttpResponse.
    """
    page_size  = PAPER_MAP.get(paper, PAPER_MAP[DEFAULT_PAPER])
    page_width, page_height = page_size

    styles = _make_styles()

    # -- Document setup --
    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=MARGIN_LEFT,
        rightMargin=MARGIN_RIGHT,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
    )

    frame = Frame(
        MARGIN_LEFT,
        MARGIN_BOTTOM,
        page_width  - MARGIN_LEFT - MARGIN_RIGHT,
        page_height - MARGIN_TOP  - MARGIN_BOTTOM,
        id="main",
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=frame)])

    # -- Assemble flowables --
    story = []
    story += _build_header_block(ctx, styles)
    story += _build_meta_block(ctx, styles, page_width)

    if ctx.get("rows"):
        story += _build_detail_table(ctx, styles)
        story += _build_summary_block(ctx, styles, page_width)
    else:
        story += _build_no_data_block(styles)

    story += _build_signature_block(styles, page_width)

    # -- Build PDF using numbered canvas --
    doc.build(story, canvasmaker=_NumberedCanvas)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes