"""Build a bilingual (AR/EN) Bill of Quantities as an .xlsx workbook.

Pure formatting — given the RFP document and its scope lines with the BoQ lines
to include, returns the workbook bytes. The router decides which lines to pass
(approved-only by default).
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# (header text — EN over AR, column width)
COLUMNS = [
    ("Item Code\nرمز البند", 16),
    ("Description (EN)\nالوصف (إنجليزي)", 36),
    ("Description (AR)\nالوصف (عربي)", 36),
    ("Unit\nالوحدة", 10),
    ("Qty\nالكمية", 10),
    ("Unit Price\nسعر الوحدة", 14),
    ("Total\nالإجمالي", 16),
    ("Brand / Comments\nالعلامة / ملاحظات", 22),
]
NCOLS = len(COLUMNS)
MONEY_FMT = "#,##0.00"

_HEADER_FILL = PatternFill("solid", fgColor="1A56DB")
_GROUP_FILL = PatternFill("solid", fgColor="EEF2FF")
_TOTAL_FILL = PatternFill("solid", fgColor="F3F4F6")
_thin = Side(style="thin", color="D0D0D0")
_BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)


def _f(value) -> float:
    return float(value or 0)


def build_boq_workbook(filename: str, groups: list) -> bytes:
    """groups: list of (scope_line, [boq_line, ...]) — only non-empty groups."""
    wb = Workbook()
    ws = wb.active
    ws.title = "BoQ"

    # Title + meta
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=NCOLS)
    title = ws.cell(row=1, column=1, value="Bill of Quantities — جدول الكميات")
    title.font = Font(bold=True, size=16)
    title.alignment = Alignment(horizontal="center")

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=NCOLS)
    meta = ws.cell(
        row=2,
        column=1,
        value=f"Source: {filename}    Generated: {datetime.now():%Y-%m-%d %H:%M}",
    )
    meta.font = Font(size=9, color="666666")
    meta.alignment = Alignment(horizontal="center")

    # Header row
    header_row = 4
    for c, (text, width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=header_row, column=c, value=text)
        cell.font = Font(bold=True, color="FFFFFF", size=10)
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _BORDER
        ws.column_dimensions[get_column_letter(c)].width = width
    ws.row_dimensions[header_row].height = 30

    row = header_row + 1
    grand_total = 0.0

    for scope, lines in groups:
        # Scope-line group header (merged, shaded), bilingual.
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
        qty_unit = f"{scope.quantity or ''} {scope.unit or ''}".strip()
        label = f"Scope #{scope.line_no} ({qty_unit}):  {scope.description}"
        gcell = ws.cell(row=row, column=1, value=label)
        gcell.font = Font(bold=True, size=10)
        gcell.fill = _GROUP_FILL
        gcell.alignment = Alignment(horizontal="left", wrap_text=True)
        for c in range(1, NCOLS + 1):
            ws.cell(row=row, column=c).border = _BORDER
        row += 1

        subtotal = 0.0
        for bl in lines:
            brand_cell = " · ".join(
                p for p in (bl.brand, getattr(bl, "subcontractor", None)) if p
            )
            values = [
                bl.item_code or "—",
                bl.description_en or "",
                bl.description_ar or "",
                bl.unit or "",
                _f(bl.quantity),
                _f(bl.unit_price),
                _f(bl.line_total),
                brand_cell,
            ]
            for c, v in enumerate(values, start=1):
                cell = ws.cell(row=row, column=c, value=v)
                cell.border = _BORDER
                cell.alignment = Alignment(
                    vertical="top",
                    wrap_text=c in (2, 3),
                    horizontal="right" if c in (3, 5, 6, 7) else "left",
                )
                if c in (6, 7):
                    cell.number_format = MONEY_FMT
            subtotal += _f(bl.line_total)
            row += 1

        # Subtotal row for this scope line
        scell = ws.cell(row=row, column=6, value="Subtotal — مجموع جزئي")
        scell.font = Font(bold=True, italic=True, size=9)
        scell.alignment = Alignment(horizontal="right")
        tcell = ws.cell(row=row, column=7, value=round(subtotal, 2))
        tcell.font = Font(bold=True)
        tcell.number_format = MONEY_FMT
        for c in range(1, NCOLS + 1):
            ws.cell(row=row, column=c).border = _BORDER
        row += 1
        grand_total += subtotal

    # Grand total
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    gt_label = ws.cell(row=row, column=1, value="GRAND TOTAL — الإجمالي الكلي")
    gt_label.font = Font(bold=True, size=12)
    gt_label.alignment = Alignment(horizontal="right")
    gt_label.fill = _TOTAL_FILL
    gt_val = ws.cell(row=row, column=7, value=round(grand_total, 2))
    gt_val.font = Font(bold=True, size=12)
    gt_val.number_format = MONEY_FMT
    gt_val.fill = _TOTAL_FILL
    for c in range(1, NCOLS + 1):
        ws.cell(row=row, column=c).border = _BORDER

    ws.freeze_panes = "A5"  # keep title + header visible while scrolling

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
