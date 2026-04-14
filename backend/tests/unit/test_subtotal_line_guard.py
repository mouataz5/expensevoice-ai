"""Garde-fous Σ lignes vs sous-total (tables OCR mal colonnées)."""
from __future__ import annotations

import pytest

from app.schemas.invoice_pipeline import InvoiceExtractionDraft, InvoiceLineDraft
from app.utils.post_processing import reconcile_subtotal_from_line_items


def test_reconcile_subtotal_does_not_replace_when_line_sum_absurd_vs_subtotal() -> None:
    """Cas devis Abdouli : lignes à qté=1 et PU gonflés → Σ HT >> HT OCR."""
    lines = [
        InvoiceLineDraft(description="A", quantity=1.0, unit_price=1_800_000.0, line_subtotal=1_800_000.0),
        InvoiceLineDraft(description="B", quantity=1.0, unit_price=229_000.0, line_subtotal=229_000.0),
    ]
    d = InvoiceExtractionDraft(
        subtotal_amount=44_723.0,
        tax_amount=8_407.07,
        total_amount=53_137.07,
        items=lines,
    )
    out, journal = reconcile_subtotal_from_line_items(d)
    assert out.subtotal_amount == pytest.approx(44_723.0)
    assert "subtotal_from_coherent_lines" not in journal


def test_reconcile_subtotal_still_snaps_when_lines_match_subtotal() -> None:
    lines = [
        InvoiceLineDraft(description="X", quantity=10.0, unit_price=100.0, line_subtotal=1_000.0),
        InvoiceLineDraft(description="Y", quantity=2.0, unit_price=250.0, line_subtotal=500.0),
    ]
    d = InvoiceExtractionDraft(subtotal_amount=1_498.0, total_amount=2_000.0, items=lines)
    out, journal = reconcile_subtotal_from_line_items(d)
    assert out.subtotal_amount == pytest.approx(1_500.0)
    assert "subtotal_snapped_to_lines" in journal or "subtotal_from_coherent_lines" in journal
