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
C_GREEN_DARK   = colors.HexColor("#1B5E20")   # header background
C_GREEN_MID    = colors.HexColor("#2E7D32")   # section title bg
C_GREEN_LIGHT  = colors.HexColor("#E8F5E9")   # alternating row
C_GREEN_BORDER = colors.HexColor("#A5D6A7")   # table borders
C_WHITE        = colors.white
C_BLACK        = colors.HexColor("#1C2526")
C_GREY         = colors.HexColor("#546E7A")
C_TOTAL_BG     = colors.HexColor("#F1F8E9")   # totals section background
C_TTC_BG       = colors.HexColor("#C8E6C9")   # TTC highlight

PAGE_W, PAGE_H = A4
MARGIN_H = 18 * mm
MARGIN_V = 18 * mm


def _pdf_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(C_GREY)
    canvas.drawCentredString(
        PAGE_W / 2,
        10 * mm,
        "Abes AgroTech — rapport confidentiel — ne contient pas le texte brut OCR",
    )
    canvas.drawRightString(PAGE_W - MARGIN_H, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _report_title(document_type: str) -> str:
    dt = (document_type or "invoice").lower().strip()
    if dt in ("quote", "devis", "quotation"):
        return "Rapport de devis"
    return "Rapport de document fiscal"


def _extraction_status_badge(extracted: dict) -> str:
    try:
        c = float(extracted.get("confidence") or 0)
    except (TypeError, ValueError):
        c = 0.0
    if c >= 0.75:
        return "Extraction : fiable"
    if c >= 0.45:
        return "Extraction : à contrôler"
    return "Extraction : faible confiance"

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


def _fmt_tnd(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):,.3f} TND"
    except (TypeError, ValueError):
        return "—"


def _fmt_num(v: Any) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
        return f"{f:,.3f}" if f != int(f) else f"{int(f):,}"
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
    base = getSampleStyleSheet()
    latin = "Helvetica"
    latin_bold = "Helvetica-Bold"

    def ps(name, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, **kw)

    return {
        "header_title": ps(
            "header_title",
            fontName=latin_bold,
            fontSize=14,
            textColor=C_WHITE,
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "header_sub": ps(
            "header_sub",
            fontName=latin,
            fontSize=9,
            textColor=colors.HexColor("#C8E6C9"),
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "section_title": ps(
            "section_title",
            fontName=latin_bold,
            fontSize=9,
            textColor=C_WHITE,
            spaceAfter=0,
        ),
        "label": ps(
            "label",
            fontName=latin_bold,
            fontSize=8,
            textColor=C_GREY,
        ),
        "value": ps(
            "value",
            fontName=latin,
            fontSize=9,
            textColor=C_BLACK,
        ),
        "value_bold": ps(
            "value_bold",
            fontName=latin_bold,
            fontSize=9,
            textColor=C_BLACK,
        ),
        "col_head": ps(
            "col_head",
            fontName=latin_bold,
            fontSize=8,
            textColor=C_WHITE,
            alignment=TA_CENTER,
        ),
        "cell": ps(
            "cell",
            fontName=latin,
            fontSize=8,
            textColor=C_BLACK,
            alignment=TA_LEFT,
        ),
        "cell_r": ps(
            "cell_r",
            fontName=latin,
            fontSize=8,
            textColor=C_BLACK,
            alignment=TA_RIGHT,
        ),
        "total_label": ps(
            "total_label",
            fontName=latin_bold,
            fontSize=9,
            textColor=C_BLACK,
            alignment=TA_RIGHT,
        ),
        "total_value": ps(
            "total_value",
            fontName=latin,
            fontSize=9,
            textColor=C_BLACK,
            alignment=TA_RIGHT,
        ),
        "ttc_label": ps(
            "ttc_label",
            fontName=latin_bold,
            fontSize=11,
            textColor=C_GREEN_DARK,
            alignment=TA_RIGHT,
        ),
        "ttc_value": ps(
            "ttc_value",
            fontName=latin_bold,
            fontSize=11,
            textColor=C_GREEN_DARK,
            alignment=TA_RIGHT,
        ),
        "footer": ps(
            "footer",
            fontName=latin,
            fontSize=7,
            textColor=C_GREY,
            alignment=TA_CENTER,
        ),
        "page2_title": ps(
            "page2_title",
            fontName=latin_bold,
            fontSize=12,
            textColor=C_GREEN_DARK,
            alignment=TA_CENTER,
            spaceAfter=4 * mm,
        ),
        "summary": ps(
            "summary",
            fontName=latin,
            fontSize=9,
            textColor=C_BLACK,
            alignment=TA_LEFT,
            spaceAfter=3 * mm,
        ),
        "warn_title": ps(
            "warn_title",
            fontName=latin_bold,
            fontSize=9,
            textColor=C_GREEN_DARK,
            alignment=TA_LEFT,
            spaceAfter=2 * mm,
        ),
        "warn_item": ps(
            "warn_item",
            fontName=latin,
            fontSize=8,
            textColor=C_BLACK,
            alignment=TA_LEFT,
            leftIndent=6,
        ),
    }


# ─── Section title row (full-width green bar) ─────────────────────────────────

def _section_bar(title: str, styles: dict, col_span: int = 2) -> Table:
    t = Table([[Paragraph(title, styles["section_title"])]], colWidths=[PAGE_W - 2 * MARGIN_H])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_GREEN_MID),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_GREEN_MID]),
    ]))
    return t


def _info_row(label: str, value: str, styles: dict) -> list:
    return [
        Paragraph(label, styles["label"]),
        Paragraph(value or "—", styles["value"]),
    ]


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
        bottomMargin=MARGIN_V + 12 * mm,
        title="Rapport document — Abes AgroTech",
        author="Abes AgroTech",
    )

    story = []
    content_w = PAGE_W - 2 * MARGIN_H

    # ══════════════════════════════════════════════════════
    # HEADER BLOCK
    # ══════════════════════════════════════════════════════
    doc_type = _safe(extracted.get("document_type")) or "invoice"
    rep_title = _report_title(doc_type)
    logo_cell = Table(
        [[Paragraph('<font color="white" size="11"><b>A</b></font>', styles["header_title"])]],
        colWidths=[10 * mm],
        rowHeights=[10 * mm],
    )
    logo_cell.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_GREEN_MID),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, C_WHITE),
    ]))
    title_stack = Table(
        [
            [Paragraph("Abes AgroTech", styles["header_title"])],
            [Paragraph(rep_title + " / تقرير المستند", styles["header_sub"])],
        ],
        colWidths=[content_w - 12 * mm],
    )
    title_stack.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    header_data = [[logo_cell, title_stack]]
    header_table = Table(header_data, colWidths=[12 * mm, content_w - 12 * mm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_GREEN_DARK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROUNDEDCORNERS", [4, 4, 0, 0]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 3 * mm))

    # ══════════════════════════════════════════════════════
    # INFO BAR: employee + date | invoice ref
    # ══════════════════════════════════════════════════════
    scan_date = _fmt_date(created_at_str)
    inv_number = _safe(extracted.get("invoice_number")) or "—"
    inv_date = _fmt_date(_safe(extracted.get("invoice_date")) or None)
    doc_label = "N° devis / réf." if doc_type.lower() in ("quote", "devis", "quotation") else "N° document"
    type_doc_fr = (
        "Devis"
        if doc_type.lower() in ("quote", "devis", "quotation")
        else "Facture / document"
    )

    info_data = [
        [
            Paragraph("Collaborateur", styles["label"]),
            Paragraph(employee_email or "—", styles["value"]),
            Paragraph(doc_label, styles["label"]),
            Paragraph(inv_number, styles["value_bold"]),
        ],
        [
            Paragraph("Date de numérisation", styles["label"]),
            Paragraph(scan_date, styles["value"]),
            Paragraph("Date document", styles["label"]),
            Paragraph(inv_date, styles["value_bold"]),
        ],
        [
            Paragraph("Type de transaction", styles["label"]),
            Paragraph(_transaction_label(transaction_type), styles["value_bold"]),
            Paragraph("Nature du document", styles["label"]),
            Paragraph(type_doc_fr, styles["value_bold"]),
        ],
        [
            Paragraph("Statut", styles["label"]),
            Paragraph(_extraction_status_badge(extracted), styles["value_bold"]),
            Paragraph("Confiance globale", styles["label"]),
            Paragraph(
                (
                    f"{float(extracted.get('confidence') or 0) * 100:.0f} %"
                    if extracted.get("confidence") is not None
                    else "—"
                ),
                styles["value"],
            ),
        ],
    ]
    col_w = content_w / 4
    info_table = Table(info_data, colWidths=[col_w * 0.9, col_w * 1.4, col_w * 0.8, col_w * 0.9])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_GREEN_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, C_GREEN_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, C_GREEN_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        # vertical separator between left/right halves
        ("LINEAFTER", (1, 0), (1, -1), 1, C_GREEN_BORDER),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 3 * mm))

    cur_sym = "TND" if str(extracted.get("currency") or "TND").upper() == "TND" else _safe(extracted.get("currency"))
    story.append(
        Paragraph(
            f"<b>Résumé</b> — Les montants sont affichés en {cur_sym}. "
            "Ce rapport présente une synthèse structurée ; le texte OCR brut n’est pas reproduit ici.",
            styles["summary"],
        )
    )
    story.append(Spacer(1, 2 * mm))

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

    def _info_cell(rows: list[tuple[str, str]]) -> Table:
        data = [[Paragraph(lbl, styles["label"]), Paragraph(val, styles["value"])] for lbl, val in rows]
        t = Table(data, colWidths=[30 * mm, content_w / 2 - 36 * mm])
        t.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        return t

    sup_cell = _info_cell([
        ("Nom commercial:", supplier_name),
        ("Raison sociale / enseigne:", supplier_fn),
        ("MF / RNE:", sup_tax),
        ("Adresse / ville:", sup_addr),
        ("Téléphone:", sup_tel),
    ])
    cli_cell = _info_cell([
        ("Client:", client_name),
        ("Matricule fiscal:", client_cin),
        ("Adresse:", client_addr),
        ("", ""),
    ])

    half = content_w / 2 - 3 * mm
    sup_block = Table(
        [[Paragraph("Fournisseur / المورد", styles["section_title"])], [sup_cell]],
        colWidths=[half],
    )
    sup_block.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_GREEN_MID),
        ("BACKGROUND", (0, 1), (-1, -1), C_WHITE),
        ("BOX", (0, 0), (-1, -1), 0.5, C_GREEN_BORDER),
        ("TOPPADDING", (0, 0), (-1, 0), 4),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
    ]))

    cli_block = Table(
        [[Paragraph("Client / الحريف", styles["section_title"])], [cli_cell]],
        colWidths=[half],
    )
    cli_block.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_GREEN_MID),
        ("BACKGROUND", (0, 1), (-1, -1), C_WHITE),
        ("BOX", (0, 0), (-1, -1), 0.5, C_GREEN_BORDER),
        ("TOPPADDING", (0, 0), (-1, 0), 4),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
    ]))

    two_col = Table([[sup_block, cli_block]], colWidths=[half + 3 * mm, half])
    two_col.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 3),
        ("RIGHTPADDING", (1, 0), (1, -1), 0),
    ]))
    story.append(two_col)
    story.append(Spacer(1, 5 * mm))

    # ══════════════════════════════════════════════════════
    # ITEMS TABLE
    # ══════════════════════════════════════════════════════
    story.append(_section_bar("Détail des articles / تفاصيل المواد", styles))
    story.append(Spacer(1, 1 * mm))

    def _ph(txt: str, st: str) -> Paragraph:
        return Paragraph(txt, styles[st])

    items = extracted.get("items") or []
    has_line_ttc = any(
        _parse_line_ttc_from_details(str(row.get("details") or "")) is not None for row in items
    )

    if has_line_ttc:
        cw = [
            content_w * 0.32,
            content_w * 0.08,
            content_w * 0.10,
            content_w * 0.15,
            content_w * 0.14,
            content_w * 0.21,
        ]
        items_header = [
            _ph("Désignation", "col_head"),
            _ph("Qté", "col_head"),
            _ph("Unité", "col_head"),
            _ph("P.U.", "col_head"),
            _ph("Montant HT", "col_head"),
            _ph("Montant TTC", "col_head"),
        ]
    else:
        cw = [content_w * 0.38, content_w * 0.10, content_w * 0.13, content_w * 0.18, content_w * 0.21]
        items_header = [
            _ph("Désignation", "col_head"),
            _ph("Qté", "col_head"),
            _ph("Unité", "col_head"),
            _ph("Prix Unit.", "col_head"),
            _ph("Montant HT", "col_head"),
        ]
    items_rows = [items_header]

    for idx, row in enumerate(items[:30]):
        desig = _safe(row.get("designation")) or "—"
        qty = row.get("quantity")
        unit = _safe(row.get("unit")) or "—"
        up = row.get("unit_price")
        amt = row.get("line_total")
        if amt is None and qty is not None and up is not None:
            try:
                amt = float(qty) * float(up)
            except (TypeError, ValueError):
                amt = None
        l_ttc = _parse_line_ttc_from_details(str(row.get("details") or ""))
        if has_line_ttc:
            items_rows.append([
                _ph(desig[:55], "cell"),
                _ph(_fmt_num(qty), "cell_r"),
                _ph(unit[:12], "cell"),
                _ph(_fmt_num(up), "cell_r"),
                _ph(_fmt_num(amt), "cell_r"),
                _ph(_fmt_num(l_ttc), "cell_r"),
            ])
        else:
            items_rows.append([
                _ph(desig[:55], "cell"),
                _ph(_fmt_num(qty), "cell_r"),
                _ph(unit[:12], "cell"),
                _ph(_fmt_num(up), "cell_r"),
                _ph(_fmt_num(amt), "cell_r"),
            ])

    if not items:
        ncols = 6 if has_line_ttc else 5
        items_rows.append(
            [_ph("Aucun article extrait", "cell")]
            + [_ph("", "cell") for _ in range(ncols - 1)]
        )

    items_table = Table(items_rows, colWidths=cw, repeatRows=1)
    row_count = len(items_rows)
    ts = [
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), C_GREEN_MID),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        # Body
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
        # Grid
        ("BOX", (0, 0), (-1, -1), 0.5, C_GREEN_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, C_GREEN_BORDER),
        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        # Alternating rows
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_GREEN_LIGHT]),
    ]
    items_table.setStyle(TableStyle(ts))
    story.append(items_table)
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════
    # TOTALS BOX (right-aligned)
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
            ttc = sum(float(it.get("line_total") or 0) for it in items)
        except (TypeError, ValueError):
            ttc = None

    ext = extracted.get("extraction") if isinstance(extracted.get("extraction"), dict) else {}
    tax_rate = extracted.get("tax_rate_percent")
    if tax_rate is None:
        tax_rate = ext.get("tax_rate_percent")
    tva_lbl = "TVA:"
    try:
        if tax_rate is not None and float(tax_rate) > 0:
            tva_lbl = f"TVA ({float(tax_rate):g} %):"
    except (TypeError, ValueError):
        pass

    totals_data = [
        [Paragraph("Total HT / HTVA:", styles["total_label"]), Paragraph(_fmt_tnd(htva), styles["total_value"])],
        [Paragraph(tva_lbl, styles["total_label"]), Paragraph(_fmt_tnd(tva), styles["total_value"])],
    ]
    show_timbre = timbre is not None
    try:
        show_timbre = show_timbre and float(timbre) > 0  # type: ignore[arg-type]
    except (TypeError, ValueError):
        show_timbre = False
    if show_timbre:
        totals_data.append(
            [Paragraph("Timbre:", styles["total_label"]), Paragraph(_fmt_tnd(timbre), styles["total_value"])]
        )
    ttc_row_idx = len(totals_data)
    totals_data.append(
        [Paragraph("Total TTC:", styles["ttc_label"]), Paragraph(_fmt_tnd(ttc), styles["ttc_value"])]
    )
    tot_col1 = 35 * mm
    tot_col2 = 45 * mm
    totals_inner = Table(totals_data, colWidths=[tot_col1, tot_col2])
    last_i = len(totals_data) - 1
    pre_ttc = last_i - 1
    ts_tot: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, pre_ttc), C_TOTAL_BG),
        ("BACKGROUND", (0, ttc_row_idx), (-1, ttc_row_idx), C_TTC_BG),
        ("BOX", (0, 0), (-1, -1), 0.75, C_GREEN_BORDER),
        ("LINEABOVE", (0, ttc_row_idx), (-1, ttc_row_idx), 1.0, C_GREEN_MID),
        ("INNERGRID", (0, 0), (-1, pre_ttc), 0.25, C_GREEN_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    totals_inner.setStyle(TableStyle(ts_tot))

    # Place totals right-aligned using spacer + inner table
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

    user_warn = list(extracted.get("user_warnings") or [])
    if user_warn:
        story.append(Paragraph("Points d’attention", styles["warn_title"]))
        for uw in user_warn[:10]:
            story.append(Paragraph(f"• {_safe(uw)}", styles["warn_item"]))
        story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_GREEN_BORDER))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Document généré par Abes AgroTech. Les montants proviennent de l’analyse du scan ; "
        "une validation métier reste recommandée avant toute décision financière.",
        styles["footer"],
    ))

    # ══════════════════════════════════════════════════════
    # PAGE 2: Invoice image
    # ══════════════════════════════════════════════════════
    if image_path and Path(image_path).is_file():
        story.append(PageBreak())
        story.append(Paragraph("Annexe — copie du document source (scan)", styles["page2_title"]))
        story.append(HRFlowable(width="100%", thickness=1, color=C_GREEN_MID))
        story.append(Spacer(1, 4 * mm))
        try:
            avail_w = content_w
            avail_h = PAGE_H - 2 * MARGIN_V - 30 * mm
            from reportlab.lib.utils import ImageReader
            ir = ImageReader(image_path)
            iw, ih = ir.getSize()
            if iw and ih:
                scale = min(avail_w / iw, avail_h / ih, 1.0)
                nw, nh = iw * scale, ih * scale
            else:
                nw, nh = avail_w, avail_h
            img = Image(image_path, width=nw, height=nh)
            img.hAlign = "CENTER"
            story.append(img)
        except Exception as exc:
            logger.warning("Could not embed invoice image: %s", exc)
            story.append(Paragraph("Image non disponible / الصورة غير متوفرة", styles["footer"]))

    # ══════════════════════════════════════════════════════
    # BUILD
    # ══════════════════════════════════════════════════════
    doc.build(story, onFirstPage=_pdf_footer, onLaterPages=_pdf_footer)
    logger.info("Invoice PDF generated: %s", pdf_output_path)
