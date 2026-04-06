"""Reconstruction tableau par géométrie des mots (sans surya-ocr)."""
from __future__ import annotations

from app.schemas.invoice_pipeline import OCRLineSpan, OCRResult, OCRWordSpan
from app.services.invoice_facades.geometry_table_extractor import (
    extract_invoice_lines_from_word_geometry,
    score_line_drafts,
)


def _w(text: str, x0: float, y0: float, x1: float, y1: float) -> OCRWordSpan:
    return OCRWordSpan(text=text, bbox=(x0, y0, x1, y1))


def test_geometry_extracts_qty_and_ht_from_synthetic_grid():
    """Grille synthétique type devis : en-tête + une ligne avec qté=3, PU=100, HT=300."""
    y = 100.0
    dy = 28.0
    hdr = OCRLineSpan(
        text="",
        words=[
            _w("Designation", 20, y, 110, y + 18),
            _w("UN", 200, y, 230, y + 18),
            _w("QTE", 240, y, 280, y + 18),
            _w("P.U", 300, y, 340, y + 18),
            _w("P.HT", 360, y, 410, y + 18),
            _w("P.TTC", 430, y, 490, y + 18),
        ],
    )
    y2 = y + dy
    row = OCRLineSpan(
        text="",
        words=[
            _w("Produit", 20, y2, 100, y2 + 18),
            _w("UN", 200, y2, 228, y2 + 18),
            _w("3", 250, y2, 265, y2 + 18),
            _w("100", 310, y2, 340, y2 + 18),
            _w("300", 375, y2, 410, y2 + 18),
            _w("357", 450, y2, 490, y2 + 18),
        ],
    )
    ocr = OCRResult(raw_text="x", lines=[hdr, row], words=[], metadata={"provider": "surya"})
    drafts, dbg = extract_invoice_lines_from_word_geometry(ocr, metadata=ocr.metadata)
    assert dbg.get("applied_to_draft"), dbg
    assert len(drafts) == 1
    assert float(drafts[0].quantity or 0) == 3.0
    assert abs(float(drafts[0].unit_price or 0) - 100.0) < 0.01
    assert abs(float(drafts[0].line_subtotal or 0) - 300.0) < 0.01


def test_score_line_drafts_prefers_coherent_qty():
    from app.schemas.invoice_pipeline import InvoiceLineDraft

    bad = [InvoiceLineDraft(description="A", quantity=1, unit_price=1, line_subtotal=500)]
    good = [InvoiceLineDraft(description="A", quantity=5, unit_price=100, line_subtotal=500)]
    assert score_line_drafts(good) > score_line_drafts(bad)
