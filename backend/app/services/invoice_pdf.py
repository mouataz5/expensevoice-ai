"""
Professional bilingual (French/Arabic labels) invoice report PDF.
Uses ReportLab Platypus Tables for clean, structured layout.
Green/white Agriculture SaaS theme. Arabic labels fallback to French gracefully.
"""
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# ─── Brand palette ────────────────────────────────────────────────────────────
C_GREEN_DARK   = colors.HexColor("#1B5E20")
C_GREEN_MID    = colors.HexColor("#2E7D32")
C_GREEN_LIGHT  = colors.HexColor("#E8F5E9")
C_GREEN_BORDER = colors.HexColor("#A5D6A7")
C_GREEN_ACCENT = colors.HexColor("#66BB6A")
C_WHITE        = colors.white
C_BLACK        = colors.HexColor("#212121")
C_GREY         = colors.HexColor("#546E7A")
C_GREY_LIGHT   = colors.HexColor("#ECEFF1")
C_TOTAL_BG     = colors.HexColor("#F1F8E9")
C_TTC_BG       = colors.HexColor("#C8E6C9")
C_WARN_BG      = colors.HexColor("#FFF8E1")
C_WARN_BORDER  = colors.HexColor("#FFB300")
C_BADGE_HIGH   = colors.HexColor("#2E7D32")
C_BADGE_MED    = colors.HexColor("#F57F17")
C_BADGE_LOW    = colors.HexColor("#C62828")

PAGE_W, PAGE_H = A4
MARGIN_H = 16 * mm
MARGIN_V = 16 * mm


def _pdf_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(C_GREY)
    canvas.drawCentredString(
        PAGE_W / 2, 9 * mm,
        "Abes AgroTech — rapport confidentiel — ne contient pas le texte brut OCR",
    )
    canvas.drawRightString(PAGE_W - MARGIN_H, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _report_title(document_type: str) -> str:
    dt = (document_type or "invoice").lower().strip()
    if dt in ("quote", "devis", "quotation"):
        return "Rapport de Devis"
    if dt in ("delivery_note", "bon_livraison"):
        return "Rapport de Bon de Livraison"
    return "Rapport de Facture"


def _confidence_level(c: float) -> tuple[str, Any]:
    if c >= 0.75:
        return "Fiable", C_BADGE_HIGH
    if c >= 0.45:
        return "À contrôler", C_BADGE_MED
    return "Faible", C_BADGE_LOW


# ─── Arabic font (optional) ───────────────────────────────────────────────────
_ARABIC_FONT = "ArabicFont"
_arabic_loaded = False


def _try_load_arabic_font() -> bool:
    global _arabic_loaded
    if _arabic_loaded:
        return True
    font_path = os.getenv("ARABIC_FONT_PATH")
    if not font_path:
        base = Path(__file__).resolve().parent.parent.parent
        for name in (
            "NotoNaskhArabic-Regular.ttf",
            "Amiri-Regular.ttf",
            "NotoSansArabic-Regular.ttf",
        ):
            candidate = base / "fonts" / name
            if candidate.is_file():
                font_path = str(candidate)
                break
    if not font_path or not Path(font_path).is_file():
        return False
    try:
        pdfmetrics.registerFont(TTFont(_ARABIC_FONT, font_path))
        _arabic_loaded = True
        return True
    except Exception as exc:
        logger.debug("Arabic font not loaded: %s", exc)
        return False


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _safe(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _fmt_tn_millimes(v: float) -> str:
    neg = v < 0
    v = abs(float(v))
    milli = int(round(v * 1000.0 + 1e-9))
    ip = milli // 1000
    frac = milli % 1000
    s = str(ip)
    parts: list[str] = []
    while s:
        parts.append(s[-3:])
        s = s[:-3]
    int_fmt = " ".join(reversed(parts))
    body = f"{int_fmt},{frac:03d}"
    return f"{'-' if neg else ''}{body}"


def _fmt_tnd(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{_fmt_tn_millimes(float(v))} TND"
    except (TypeError, ValueError):
        return "—"


def _fmt_num(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return _fmt_tn_millimes(float(v))
    except (TypeError, ValueError):
        return _safe(v)


def _parse_line_ttc_from_details(details: str | None) -> float | None:
    if not details:
        return None
    m = re.search(r"(?i)ttc:\s*([\d\s.,]+)", details)
    if not m:
        return None
    raw = m.group(1).replace(" ", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _fmt_date(d: str | None) -> str:
    if not d:
        return "—"
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(d, fmt).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return d


def _transaction_label(tt: str) -> str:
    if tt == "sell":
        return "Vente (بيع)"
    return "Achat (شراء)"


# ─── Paragraph styles ─────────────────────────────────────────────────────────

def _build_styles(arabic_available: bool) -> dict:
    latin = "Helvetica"
    latin_bold = "Helvetica-Bold"

    def ps(name, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, **kw)

    return {
        "header_title": ps("header_title", fontName=latin_bold, fontSize=16, textColor=C_WHITE, alignment=TA_LEFT, spaceAfter=0),
        "header_sub": ps("header_sub", fontName=latin, fontSize=9, textColor=colors.HexColor("#C8E6C9"), alignment=TA_LEFT, spaceAfter=0),
        "section_title": ps("section_title", fontName=latin_bold, fontSize=9, textColor=C_WHITE, spaceAfter=0),
        "label": ps("label", fontName=latin_bold, fontSize=7.5, textColor=C_GREY),
        "value": ps("value", fontName=latin, fontSize=9, textColor=C_BLACK),
        "value_bold": ps("value_bold", fontName=latin_bold, fontSize=9, textColor=C_BLACK),
        "value_large": ps("value_large", fontName=latin_bold, fontSize=10, textColor=C_BLACK),
        "col_head": ps("col_head", fontName=latin_bold, fontSize=7.5, textColor=C_WHITE, alignment=TA_CENTER),
        "cell": ps("cell", fontName=latin, fontSize=7.5, textColor=C_BLACK, alignment=TA_LEFT),
        "cell_r": ps("cell_r", fontName=latin, fontSize=7.5, textColor=C_BLACK, alignment=TA_RIGHT),
        "cell_num": ps("cell_num", fontName=latin, fontSize=7.5, textColor=C_GREY, alignment=TA_CENTER),
        "total_label": ps("total_label", fontName=latin_bold, fontSize=9, textColor=C_BLACK, alignment=TA_RIGHT),
        "total_value": ps("total_value", fontName=latin, fontSize=9, textColor=C_BLACK, alignment=TA_RIGHT),
        "ttc_label": ps("ttc_label", fontName=latin_bold, fontSize=12, textColor=C_GREEN_DARK, alignment=TA_RIGHT),
        "ttc_value": ps("ttc_value", fontName=latin_bold, fontSize=12, textColor=C_GREEN_DARK, alignment=TA_RIGHT),
        "footer": ps("footer", fontName=latin, fontSize=7, textColor=C_GREY, alignment=TA_CENTER),
        "page2_title": ps("page2_title", fontName=latin_bold, fontSize=13, textColor=C_GREEN_DARK, alignment=TA_CENTER, spaceAfter=4 * mm),
        "summary": ps("summary", fontName=latin, fontSize=8, textColor=C_GREY, alignment=TA_LEFT, spaceAfter=2 * mm),
        "warn_title": ps("warn_title", fontName=latin_bold, fontSize=8.5, textColor=colors.HexColor("#E65100"), alignment=TA_LEFT, spaceAfter=1.5 * mm),
        "warn_item": ps("warn_item", fontName=latin, fontSize=7.5, textColor=C_BLACK, alignment=TA_LEFT, leftIndent=8),
        "badge_text": ps("badge_text", fontName=latin_bold, fontSize=8, textColor=C_WHITE, alignment=TA_CENTER),
        "conf_pct": ps("conf_pct", fontName=latin_bold, fontSize=20, textColor=C_GREEN_DARK, alignment=TA_CENTER),
        "conf_label": ps("conf_label", fontName=latin, fontSize=7, textColor=C_GREY, alignment=TA_CENTER),
        "empty_msg": ps("empty_msg", fontName=latin, fontSize=8, textColor=C_GREY, alignment=TA_CENTER),
    }


def _section_bar(title: str, styles: dict, content_w: float) -> Table:
    t = Table([[Paragraph(title, styles["section_title"])]], colWidths=[content_w])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_GREEN_MID),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROUNDEDCORNERS", [3, 3, 0, 0]),
    ]))
    return t


def _invoice_number_display(extracted: dict) -> str:
    v = _safe(extracted.get("invoice_number"))
    if v:
        return v
    ext = extracted.get("extraction")
    if isinstance(ext, dict):
        v2 = _safe(ext.get("invoice_number"))
        if v2:
            return v2
    return "—"


def _dynamic_table_suppress_rows_message(extracted: dict) -> str | None:
    pipe = extracted.get("pipeline") or {}
    pc = pipe.get("post_corrections") or {}
    dt = pc.get("dynamic_table") or {}
    if str(dt.get("extraction_status") or "").lower() == "low":
        return (
            "Les lignes du tableau nécessitent une vérification manuelle. "
            "Les totaux ci-dessous proviennent de l'analyse du document."
        )
    return None


def _invoice_date_display(extracted: dict) -> str | None:
    v = _safe(extracted.get("invoice_date")) or None
    if v:
        return v
    ext = extracted.get("extraction")
    if isinstance(ext, dict):
        return _safe(ext.get("invoice_date")) or None
    return None


def _ph(txt: str, st: str, styles: dict) -> Paragraph:
    return Paragraph(txt, styles[st])


# ─── Main generator ───────────────────────────────────────────────────────────

def generate_invoice_report_pdf(
    extracted: dict[str, Any],
    employee_email: str,
    created_at_str: str,
    transaction_type: str,
    image_path: str | None,
    pdf_output_path: str,
) -> None:
    """Generate A4 professional bilingual invoice report PDF."""
    arabic_ok = _try_load_arabic_font()
    styles = _build_styles(arabic_ok)

    Path(pdf_output_path).parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        pdf_output_path,
        pagesize=A4,
        leftMargin=MARGIN_H,
        rightMargin=MARGIN_H,
        topMargin=MARGIN_V,
        bottomMargin=MARGIN_V + 10 * mm,
        title="Rapport document — Abes AgroTech",
        author="Abes AgroTech",
    )

    story: list = []
    content_w = PAGE_W - 2 * MARGIN_H

    # ══════════════════════════════════════════════════════
    # HEADER
    # ══════════════════════════════════════════════════════
    doc_type = _safe(extracted.get("document_type")) or "invoice"
    rep_title = _report_title(doc_type)
    confidence = 0.0
    try:
        confidence = float(extracted.get("confidence") or 0)
    except (TypeError, ValueError):
        pass
    conf_pct = f"{confidence * 100:.0f}%"
    conf_label, conf_color = _confidence_level(confidence)

    title_col = Table([
        [Paragraph("Abes AgroTech", styles["header_title"])],
        [Paragraph(rep_title, styles["header_sub"])],
    ], colWidths=[content_w * 0.65])
    title_col.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))

    badge_inner = Table(
        [[Paragraph(conf_label, styles["badge_text"])]],
        colWidths=[22 * mm], rowHeights=[5 * mm],
    )
    badge_inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), conf_color),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("ROUNDEDCORNERS", [3, 3, 3, 3]),
    ]))

    conf_col = Table([
        [Paragraph(conf_pct, styles["conf_pct"])],
        [badge_inner],
        [Paragraph("Confiance", styles["conf_label"])],
    ], colWidths=[content_w * 0.20])
    conf_col.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    header_table = Table(
        [[title_col, conf_col]],
        colWidths=[content_w * 0.72, content_w * 0.28],
    )
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_GREEN_DARK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (0, -1), 12),
        ("RIGHTPADDING", (1, 0), (1, -1), 10),
        ("ROUNDEDCORNERS", [5, 5, 0, 0]),
    ]))
    story.append(header_table)

    # ══════════════════════════════════════════════════════
    # METADATA BAR (compact, below header)
    # ══════════════════════════════════════════════════════
    scan_date = _fmt_date(created_at_str)
    inv_number = _invoice_number_display(extracted)
    inv_date = _fmt_date(_invoice_date_display(extracted))
    doc_label = "N° Réf." if doc_type.lower() in ("quote", "devis", "quotation") else "N° Doc."
    type_doc_fr = {
        "quote": "Devis", "devis": "Devis", "quotation": "Devis",
        "delivery_note": "Bon de Livraison", "bon_livraison": "Bon de Livraison",
    }.get(doc_type.lower(), "Facture")

    meta_data = [
        [
            _ph(doc_label, "label", styles), _ph(inv_number, "value_large", styles),
            _ph("Date document", "label", styles), _ph(inv_date, "value_bold", styles),
            _ph("Transaction", "label", styles), _ph(_transaction_label(transaction_type), "value_bold", styles),
        ],
        [
            _ph("Type", "label", styles), _ph(type_doc_fr, "value_bold", styles),
            _ph("Numérisé le", "label", styles), _ph(scan_date, "value", styles),
            _ph("Par", "label", styles), _ph(employee_email or "—", "value", styles),
        ],
    ]
    cw6 = content_w / 6
    meta_table = Table(meta_data, colWidths=[cw6 * 0.6, cw6 * 1.4, cw6 * 0.8, cw6 * 1.0, cw6 * 0.7, cw6 * 1.5])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_GREEN_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, C_GREEN_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, C_GREEN_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEAFTER", (1, 0), (1, -1), 0.8, C_GREEN_BORDER),
        ("LINEAFTER", (3, 0), (3, -1), 0.8, C_GREEN_BORDER),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════
    # FOURNISSEUR / CLIENT SIDE-BY-SIDE
    # ══════════════════════════════════════════════════════
    supplier_name = _safe(extracted.get("supplier_name")) or "—"
    supplier_fn = _safe(extracted.get("supplier_full_name")) or supplier_name
    sup_tax = _safe(extracted.get("supplier_tax_number")) or _safe(extracted.get("supplier_tax_id")) or "—"
    sup_addr = _safe(extracted.get("supplier_address")) or "—"
    sup_tel = _safe(extracted.get("supplier_phone")) or "—"

    client_name = _safe(extracted.get("client_name")) or "—"
    client_cin = _safe(extracted.get("client_tax_id")) or _safe(extracted.get("client_cin")) or "—"
    client_addr = _safe(extracted.get("client_address")) or "—"

    half = content_w / 2 - 2 * mm

    def _card(title: str, rows: list[tuple[str, str]], width: float) -> Table:
        inner_data = [[Paragraph(lbl, styles["label"]), Paragraph(val, styles["value"])] for lbl, val in rows]
        inner = Table(inner_data, colWidths=[width * 0.35, width * 0.65 - 10])
        inner.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, C_GREY_LIGHT),
        ]))
        card = Table(
            [[Paragraph(title, styles["section_title"])], [inner]],
            colWidths=[width],
        )
        card.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_GREEN_MID),
            ("BACKGROUND", (0, 1), (-1, -1), C_WHITE),
            ("BOX", (0, 0), (-1, -1), 0.5, C_GREEN_BORDER),
            ("TOPPADDING", (0, 0), (-1, 0), 4),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 1), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
            ("ROUNDEDCORNERS", [3, 3, 3, 3]),
        ]))
        return card

    sup_card = _card("Fournisseur / المورد", [
        ("Nom:", supplier_name),
        ("Raison sociale:", supplier_fn if supplier_fn != supplier_name else "—"),
        ("MF / RNE:", sup_tax),
        ("Adresse:", sup_addr),
        ("Tél:", sup_tel),
    ], half)

    cli_card = _card("Client / الحريف", [
        ("Nom:", client_name),
        ("MF / CIN:", client_cin),
        ("Adresse:", client_addr),
    ], half)

    two_col = Table([[sup_card, cli_card]], colWidths=[half + 2 * mm, half + 2 * mm])
    two_col.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 2),
        ("RIGHTPADDING", (1, 0), (1, -1), 0),
    ]))
    story.append(two_col)
    story.append(Spacer(1, 5 * mm))

    # ══════════════════════════════════════════════════════
    # ITEMS TABLE
    # ══════════════════════════════════════════════════════
    story.append(_section_bar("Détail des articles / تفاصيل المواد", styles, content_w))
    story.append(Spacer(1, 1 * mm))

    items = list(extracted.get("items") or [])
    table_suppress = _dynamic_table_suppress_rows_message(extracted)
    if table_suppress:
        items = []

    has_line_ttc = any(
        _parse_line_ttc_from_details(str(row.get("details") or "")) is not None for row in items
    )

    if has_line_ttc:
        cw = [
            content_w * 0.05,   # N°
            content_w * 0.30,   # Designation
            content_w * 0.08,   # Qty
            content_w * 0.09,   # Unit
            content_w * 0.14,   # PU
            content_w * 0.14,   # HT
            content_w * 0.20,   # TTC
        ]
        items_header = [
            _ph("N°", "col_head", styles),
            _ph("Désignation", "col_head", styles),
            _ph("Qté", "col_head", styles),
            _ph("Unité", "col_head", styles),
            _ph("P.U.", "col_head", styles),
            _ph("Montant HT", "col_head", styles),
            _ph("Montant TTC", "col_head", styles),
        ]
    else:
        cw = [
            content_w * 0.05,   # N°
            content_w * 0.37,   # Designation
            content_w * 0.09,   # Qty
            content_w * 0.10,   # Unit
            content_w * 0.17,   # PU
            content_w * 0.22,   # HT
        ]
        items_header = [
            _ph("N°", "col_head", styles),
            _ph("Désignation", "col_head", styles),
            _ph("Qté", "col_head", styles),
            _ph("Unité", "col_head", styles),
            _ph("Prix Unit.", "col_head", styles),
            _ph("Montant HT", "col_head", styles),
        ]
    items_rows = [items_header]

    for idx, row in enumerate(items[:30]):
        desig = _safe(row.get("designation")) or _safe(row.get("description")) or "—"
        qty = row.get("quantity")
        unit = _safe(row.get("unit")) or "—"
        up = row.get("unit_price")
        amt = row.get("line_total") or row.get("line_subtotal")
        if amt is None and qty is not None and up is not None:
            try:
                amt = float(qty) * float(up)
            except (TypeError, ValueError):
                amt = None
        l_ttc = _parse_line_ttc_from_details(str(row.get("details") or ""))

        num_cell = _ph(str(idx + 1), "cell_num", styles)
        if has_line_ttc:
            items_rows.append([
                num_cell,
                _ph(desig[:60], "cell", styles),
                _ph(_fmt_num(qty), "cell_r", styles),
                _ph(unit[:12], "cell", styles),
                _ph(_fmt_num(up), "cell_r", styles),
                _ph(_fmt_num(amt), "cell_r", styles),
                _ph(_fmt_num(l_ttc), "cell_r", styles),
            ])
        else:
            items_rows.append([
                num_cell,
                _ph(desig[:60], "cell", styles),
                _ph(_fmt_num(qty), "cell_r", styles),
                _ph(unit[:12], "cell", styles),
                _ph(_fmt_num(up), "cell_r", styles),
                _ph(_fmt_num(amt), "cell_r", styles),
            ])

    if not items:
        ncols = 7 if has_line_ttc else 6
        empty_msg = table_suppress if table_suppress else "Aucun article extrait"
        items_rows.append(
            [_ph("", "cell", styles), _ph(empty_msg, "empty_msg", styles)]
            + [_ph("", "cell", styles) for _ in range(ncols - 2)]
        )

    items_table = Table(items_rows, colWidths=cw, repeatRows=1)
    ts = [
        ("BACKGROUND", (0, 0), (-1, 0), C_GREEN_MID),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (1, 1), (1, -1), "LEFT"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("BOX", (0, 0), (-1, -1), 0.5, C_GREEN_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, C_GREEN_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_GREEN_LIGHT]),
    ]
    items_table.setStyle(TableStyle(ts))
    story.append(items_table)
    story.append(Spacer(1, 5 * mm))

    # ══════════════════════════════════════════════════════
    # TOTALS BOX (right-aligned, prominent)
    # ══════════════════════════════════════════════════════
    totals = extracted.get("totals") or {}
    htva = totals.get("htva")
    tva = totals.get("tva")
    timbre = totals.get("timbre") or totals.get("stamp") or None
    try:
        if timbre is not None and float(timbre) <= 0:
            timbre = None
    except (TypeError, ValueError):
        timbre = None
    if timbre is None:
        try:
            sd = float(extracted.get("stamp_duty") or 0)
            timbre = sd if sd > 0 else None
        except (TypeError, ValueError):
            pass
    ttc = totals.get("ttc")
    if ttc is None and items:
        try:
            ttc = sum(float(it.get("line_total") or it.get("line_subtotal") or 0) for it in items)
        except (TypeError, ValueError):
            ttc = None

    ext = extracted.get("extraction") if isinstance(extracted.get("extraction"), dict) else {}
    tax_rate = extracted.get("tax_rate_percent")
    if tax_rate is None:
        tax_rate = ext.get("tax_rate_percent")
    tva_lbl = "TVA:"
    try:
        if tax_rate is not None and float(tax_rate) > 0:
            tva_lbl = f"TVA ({float(tax_rate):g}%):"
    except (TypeError, ValueError):
        pass

    totals_data = [
        [Paragraph("Sous-total HT:", styles["total_label"]), Paragraph(_fmt_tnd(htva), styles["total_value"])],
        [Paragraph(tva_lbl, styles["total_label"]), Paragraph(_fmt_tnd(tva), styles["total_value"])],
    ]
    show_timbre = timbre is not None
    try:
        show_timbre = show_timbre and float(timbre) > 0
    except (TypeError, ValueError):
        show_timbre = False
    if show_timbre:
        totals_data.append(
            [Paragraph("Droit de timbre:", styles["total_label"]), Paragraph(_fmt_tnd(timbre), styles["total_value"])]
        )
    ttc_row_idx = len(totals_data)
    totals_data.append(
        [Paragraph("TOTAL TTC:", styles["ttc_label"]), Paragraph(_fmt_tnd(ttc), styles["ttc_value"])]
    )

    tot_col1 = 38 * mm
    tot_col2 = 50 * mm
    totals_inner = Table(totals_data, colWidths=[tot_col1, tot_col2])
    pre_ttc = ttc_row_idx - 1
    ts_tot: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, pre_ttc), C_TOTAL_BG),
        ("BACKGROUND", (0, ttc_row_idx), (-1, ttc_row_idx), C_TTC_BG),
        ("BOX", (0, 0), (-1, -1), 1.0, C_GREEN_MID),
        ("LINEABOVE", (0, ttc_row_idx), (-1, ttc_row_idx), 1.5, C_GREEN_DARK),
        ("INNERGRID", (0, 0), (-1, pre_ttc), 0.25, C_GREEN_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [0, 0, 4, 4]),
    ]
    totals_inner.setStyle(TableStyle(ts_tot))

    spacer_w = content_w - tot_col1 - tot_col2 - 4 * mm
    totals_wrapper = Table(
        [[Paragraph("", styles["value"]), totals_inner]],
        colWidths=[spacer_w, tot_col1 + tot_col2 + 4 * mm],
    )
    totals_wrapper.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(totals_wrapper)
    story.append(Spacer(1, 5 * mm))

    # ══════════════════════════════════════════════════════
    # WARNINGS (colored alert box)
    # ══════════════════════════════════════════════════════
    user_warn = list(extracted.get("user_warnings") or [])
    if user_warn:
        warn_items_data = []
        for uw in user_warn[:8]:
            warn_items_data.append([Paragraph(f"  ⚠  {_safe(uw)}", styles["warn_item"])])
        warn_inner = Table(warn_items_data, colWidths=[content_w - 8 * mm])
        warn_inner.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ]))

        warn_box = Table([
            [Paragraph("Points d'attention", styles["warn_title"])],
            [warn_inner],
        ], colWidths=[content_w])
        warn_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), C_WARN_BG),
            ("BOX", (0, 0), (-1, -1), 1.0, C_WARN_BORDER),
            ("TOPPADDING", (0, 0), (-1, 0), 5),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ]))
        story.append(warn_box)
        story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_GREEN_BORDER))
    story.append(Spacer(1, 2 * mm))
    cur_sym = "TND" if str(extracted.get("currency") or "TND").upper() == "TND" else _safe(extracted.get("currency"))
    story.append(Paragraph(
        f"Montants en {cur_sym}. Document généré par Abes AgroTech — "
        "validation métier recommandée avant toute décision financière.",
        styles["footer"],
    ))

    # ══════════════════════════════════════════════════════
    # PAGE 2: Invoice image (with frame)
    # ══════════════════════════════════════════════════════
    if image_path and Path(image_path).is_file():
        story.append(PageBreak())
        story.append(Paragraph("Annexe — Document source (scan)", styles["page2_title"]))
        story.append(HRFlowable(width="100%", thickness=1, color=C_GREEN_MID))
        story.append(Spacer(1, 4 * mm))
        try:
            avail_w = content_w - 4 * mm
            avail_h = PAGE_H - 2 * MARGIN_V - 40 * mm
            from reportlab.lib.utils import ImageReader
            ir = ImageReader(image_path)
            iw, ih = ir.getSize()
            if iw and ih:
                scale = min(avail_w / iw, avail_h / ih, 1.0)
                nw, nh = iw * scale, ih * scale
            else:
                nw, nh = avail_w, avail_h
            img = Image(image_path, width=nw, height=nh)
            img_table = Table([[img]], colWidths=[nw + 4 * mm], rowHeights=[nh + 4 * mm])
            img_table.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 1.0, C_GREEN_BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), C_WHITE),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]))
            img_wrapper = Table([[img_table]], colWidths=[content_w])
            img_wrapper.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(img_wrapper)
        except Exception as exc:
            logger.warning("Could not embed invoice image: %s", exc)
            story.append(Paragraph("Image non disponible / الصورة غير متوفرة", styles["footer"]))

    # ══════════════════════════════════════════════════════
    # BUILD
    # ══════════════════════════════════════════════════════
    doc.build(story, onFirstPage=_pdf_footer, onLaterPages=_pdf_footer)
    logger.info("Invoice PDF generated: %s", pdf_output_path)
