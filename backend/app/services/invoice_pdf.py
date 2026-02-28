"""
Bilingual (Arabic + French) invoice report PDF — premium Agriculture SaaS style.
Headings: Arabic (FR). RTL-friendly layout. Green/white theme, clean borders.
Uses Arabic-capable font when available (e.g. Noto Naskh Arabic in fonts/).
"""
import io
import logging
import os
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

# Brand colors (Agriculture SaaS green/white)
GREEN_PRIMARY = (0.11, 0.35, 0.25)      # deep forest green
GREEN_ACCENT = (0.13, 0.45, 0.32)       # accent bar
GREEN_SOFT = (0.85, 0.94, 0.90)        # soft section background
GREEN_BORDER = (0.70, 0.85, 0.78)       # subtle border
WHITE = (1, 1, 1)
BLACK = (0.11, 0.15, 0.14)

# Bilingual labels: Arabic (French)
APP_NAME_AR = "نظام عبّاس"
APP_NAME_FR = "Rapport Facture"
HEADER_TITLE = "تقرير فاتورة (Rapport Facture)"

SECTION_EMPLOYEE = "معلومات الموظف (Infos employé)"
SECTION_TYPE = "نوع العملية (Type)"
SECTION_SUPPLIER = "المزود (Fournisseur)"
SECTION_CLIENT = "الحريف (Client)"
SECTION_INVOICE_DETAILS = "تفاصيل الفاتورة (Détails facture)"
SECTION_ITEMS = "تفاصيل المواد (Détails articles)"
SECTION_TOTALS = "الإجماليات (Totaux)"
PAGE2_TITLE = "صورة الفاتورة (Image facture)"

FOOTER_AR = "هذا التقرير تم إنشاؤه آليًا وقابل للمراجعة من طرف الإدارة"
FOOTER_FR = "Ce rapport est généré automatiquement et soumis à validation."

TT_BUY_AR = "شراء"
TT_BUY_FR = "Achat"
TT_SELL_AR = "بيع"
TT_SELL_FR = "Vente"

# Table headers bilingual
COL_DESIGNATION = "الصنف (Désignation)"
COL_QTY = "الكمية (Qté)"
COL_UNIT = "الوحدة (Unité)"
COL_PU = "سعر الوحدة (PU)"
COL_AMOUNT = "المبلغ (Montant)"

# Totals labels
TOT_HTVA = "HTVA"
TOT_TVA = "TVA"
TOT_TIMBRE = "Timbre"
TOT_TTC = "TTC"

MARGIN = 18 * mm
PAGE_W, PAGE_H = A4
TABLE_COL_WIDTHS = [88 * mm, 20 * mm, 18 * mm, 26 * mm, 30 * mm]
FONT_LATIN = "Helvetica"
FONT_LATIN_BOLD = "Helvetica-Bold"
FONT_ARABIC = "Arabic"  # registered name if TTF loaded


def _register_arabic_font() -> bool:
    """Register Arabic TTF if available. Returns True if registered."""
    font_path = os.getenv("ARABIC_FONT_PATH")
    if not font_path:
        base = Path(__file__).resolve().parent.parent.parent
        for name in ("NotoNaskhArabic-Regular.ttf", "Amiri-Regular.ttf", "NotoSansArabic-Regular.ttf"):
            candidate = base / "fonts" / name
            if candidate.is_file():
                font_path = str(candidate)
                break
    if not font_path or not Path(font_path).is_file():
        logger.debug("No Arabic font found; using Helvetica for Arabic text")
        return False
    try:
        pdfmetrics.registerFont(TTFont(FONT_ARABIC, font_path))
        return True
    except Exception as e:
        logger.warning("Could not register Arabic font %s: %s", font_path, e)
        return False


def _font_arabic(c: canvas.Canvas, size: int) -> None:
    try:
        c.setFont(FONT_ARABIC, size)
    except Exception:
        c.setFont(FONT_LATIN, size)


def _safe(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _fmt_tnd(val: Any) -> str:
    if val is None:
        return "—"
    try:
        return f"{float(val):.3f}"
    except (TypeError, ValueError):
        return "—"


def _draw_header_bar(c: canvas.Canvas, y: float, width: float) -> None:
    """Green header bar across top."""
    c.setFillColorRGB(*GREEN_ACCENT)
    c.rect(0, y - 6 * mm, width, 12 * mm, fill=1, stroke=0)
    c.setFillColorRGB(*WHITE)
    c.setFont(FONT_LATIN_BOLD, 12)
    c.drawString(MARGIN, y - 4 * mm, f"{APP_NAME_AR} — {APP_NAME_FR}")
    c.setFillColorRGB(*BLACK)


def _draw_section_title(c: canvas.Canvas, x: float, y: float, title: str, use_arabic: bool) -> float:
    """Draw section title with soft green background; return new y."""
    c.setFillColorRGB(*GREEN_SOFT)
    c.setStrokeColorRGB(*GREEN_BORDER)
    c.rect(x, y - 5 * mm, 85 * mm, 6 * mm, fill=1, stroke=1)
    c.setFillColorRGB(*GREEN_PRIMARY)
    if use_arabic:
        _font_arabic(c, 9)
    else:
        c.setFont(FONT_LATIN_BOLD, 9)
    c.drawString(x + 2 * mm, y - 4 * mm, title[:55])
    c.setFillColorRGB(*BLACK)
    c.setFont(FONT_LATIN, 8)
    return y - 6 * mm


def _draw_block_lines(c: canvas.Canvas, x: float, y: float, lines: list[str], w: float = 82 * mm) -> float:
    for line in (lines or [])[:6]:
        if line:
            c.drawString(x, y, str(line)[:48])
        y -= 4 * mm
    return y


def generate_invoice_report_pdf(
    extracted: dict[str, Any],
    employee_email: str,
    created_at_str: str,
    transaction_type: str,
    image_path: str | None,
    pdf_output_path: str,
) -> None:
    """
    Generate A4 bilingual (Arabic + French) PDF with premium green/white style.
    """
    has_arabic = _register_arabic_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - MARGIN

    # ----- Header bar -----
    _draw_header_bar(c, y + 4 * mm, width)
    y -= 14 * mm

    # ----- Section A: Employee info -----
    y = _draw_section_title(c, MARGIN, y, SECTION_EMPLOYEE, has_arabic)
    c.setFont(FONT_LATIN, 8)
    c.drawString(MARGIN, y, f"{_safe(employee_email)}")
    y -= 4 * mm
    c.drawString(MARGIN, y, _safe(created_at_str))
    y -= 8 * mm

    # ----- Section B: Transaction type -----
    y = _draw_section_title(c, MARGIN, y, SECTION_TYPE, has_arabic)
    tt_ar = TT_SELL_AR if transaction_type == "sell" else TT_BUY_AR
    tt_fr = TT_SELL_FR if transaction_type == "sell" else TT_BUY_FR
    c.drawString(MARGIN, y, f"{tt_ar} ({tt_fr})")
    y -= 8 * mm

    # ----- Section C: Supplier -----
    y = _draw_section_title(c, MARGIN, y, SECTION_SUPPLIER, has_arabic)
    supplier_name = _safe(extracted.get("supplier_name"))
    supplier_lines = [supplier_name or "—", "MF/RNE: —", "Adresse: —", "Tél: —"]
    y = _draw_block_lines(c, MARGIN, y, supplier_lines)
    y -= 4 * mm

    # ----- Section D: Client (right column) -----
    y_client_start = y + 28 * mm
    y_client_start = _draw_section_title(c, MARGIN + 92 * mm, y_client_start, SECTION_CLIENT, has_arabic)
    client_lines = ["—", "MF/CIN: —", "Adresse: —"]
    _draw_block_lines(c, MARGIN + 92 * mm, y_client_start, client_lines)
    y -= 4 * mm

    # ----- Section E: Invoice details -----
    y = _draw_section_title(c, MARGIN, y, SECTION_INVOICE_DETAILS, has_arabic)
    inv_lines = [
        f"N°: {_safe(extracted.get('invoice_number')) or '—'}",
        f"Date: {_safe(extracted.get('invoice_date')) or '—'}",
    ]
    y = _draw_block_lines(c, MARGIN, y, inv_lines)
    y -= 6 * mm

    # ----- Section F: Items table -----
    y = _draw_section_title(c, MARGIN, y, SECTION_ITEMS, has_arabic)
    c.setStrokeColorRGB(*GREEN_BORDER)
    c.setFillColorRGB(*GREEN_SOFT)
    c.rect(MARGIN, y - 5 * mm, sum(TABLE_COL_WIDTHS), 5 * mm, fill=1, stroke=1)
    c.setFillColorRGB(*GREEN_PRIMARY)
    c.setFont(FONT_LATIN_BOLD, 8)
    x0 = MARGIN + 1 * mm
    c.drawString(x0, y - 3.5 * mm, COL_DESIGNATION[:28])
    c.drawString(x0 + TABLE_COL_WIDTHS[0], y - 3.5 * mm, COL_QTY[:12])
    c.drawString(x0 + TABLE_COL_WIDTHS[0] + TABLE_COL_WIDTHS[1], y - 3.5 * mm, COL_UNIT[:10])
    c.drawString(x0 + sum(TABLE_COL_WIDTHS[:3]), y - 3.5 * mm, COL_PU[:12])
    c.drawString(x0 + sum(TABLE_COL_WIDTHS[:4]), y - 3.5 * mm, COL_AMOUNT[:12])
    y -= 6 * mm
    c.setFillColorRGB(*BLACK)
    c.setFont(FONT_LATIN, 8)

    items = extracted.get("items") or []
    for row in items[:25]:
        desig = _safe(row.get("designation"))[:32]
        qty = row.get("quantity")
        unit = "—"
        up = row.get("unit_price")
        amt = row.get("line_total")
        if qty is not None and up is not None and amt is None:
            amt = float(qty) * float(up)
        c.drawString(x0, y, desig)
        c.drawString(x0 + TABLE_COL_WIDTHS[0], y, str(qty) if qty is not None else "—")
        c.drawString(x0 + TABLE_COL_WIDTHS[0] + TABLE_COL_WIDTHS[1], y, unit)
        c.drawString(x0 + sum(TABLE_COL_WIDTHS[:3]), y, _fmt_tnd(up))
        c.drawString(x0 + sum(TABLE_COL_WIDTHS[:4]), y, _fmt_tnd(amt))
        y -= 4 * mm
        if y < 75:
            c.showPage()
            y = height - MARGIN
            c.setFont(FONT_LATIN, 8)

    y -= 6 * mm

    # ----- Section G: Totals box -----
    y = _draw_section_title(c, MARGIN, y, SECTION_TOTALS, has_arabic)
    totals = extracted.get("totals") or {}
    total_htva = totals.get("htva")
    total_tva = totals.get("tva")
    stamp_duty = None
    total_ttc = totals.get("ttc")
    if total_ttc is None and items:
        total_ttc = sum(float(it.get("line_total") or 0) for it in items)
    c.setFont(FONT_LATIN_BOLD, 8)
    c.drawString(MARGIN, y, TOT_HTVA + ":")
    c.drawString(MARGIN + 45 * mm, y, _fmt_tnd(total_htva))
    y -= 4 * mm
    c.drawString(MARGIN, y, TOT_TVA + ":")
    c.drawString(MARGIN + 45 * mm, y, _fmt_tnd(total_tva))
    y -= 4 * mm
    c.drawString(MARGIN, y, TOT_TIMBRE + ":")
    c.drawString(MARGIN + 45 * mm, y, _fmt_tnd(stamp_duty))
    y -= 4 * mm
    c.drawString(MARGIN, y, TOT_TTC + ":")
    c.drawString(MARGIN + 45 * mm, y, _fmt_tnd(total_ttc))
    y -= 8 * mm

    # ----- Footer bilingual -----
    c.setStrokeColorRGB(*GREEN_PRIMARY)
    c.setLineWidth(0.5)
    c.line(MARGIN, y + 2 * mm, width - MARGIN, y + 2 * mm)
    c.setFont(FONT_LATIN, 7)
    c.drawString(MARGIN, y, FOOTER_AR)
    y -= 3.5 * mm
    c.drawString(MARGIN, y, FOOTER_FR)
    y -= 6 * mm

    # ----- Page 2: invoice image -----
    if image_path and Path(image_path).is_file():
        c.showPage()
        y = height - MARGIN
        c.setFillColorRGB(*GREEN_PRIMARY)
        c.setFont(FONT_LATIN_BOLD, 10)
        if has_arabic:
            _font_arabic(c, 10)
        c.drawString(MARGIN, y, PAGE2_TITLE)
        c.setFillColorRGB(*BLACK)
        y -= 8 * mm
        try:
            from reportlab.lib.utils import ImageReader
            img = ImageReader(image_path)
            iw, ih = img.getSize()
            max_w = width - 2 * MARGIN
            max_h = y - MARGIN
            scale = min(max_w / iw, max_h / ih, 1.0) if iw and ih else 1.0
            nw, nh = iw * scale, ih * scale
            x_img = (width - nw) / 2
            y_img = y - nh
            c.drawImage(image_path, x_img, y_img, width=nw, height=nh)
        except Exception as e:
            logger.warning("Could not embed invoice image in PDF: %s", e)
            c.setFont(FONT_LATIN, 8)
            c.drawString(MARGIN, y - 20, "Image non disponible.")

    c.save()
    pdf_bytes = buf.getvalue()
    Path(pdf_output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(pdf_output_path).write_bytes(pdf_bytes)
    logger.info("Generated bilingual invoice PDF: %s", pdf_output_path)
