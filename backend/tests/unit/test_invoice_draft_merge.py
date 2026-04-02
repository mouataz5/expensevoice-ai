"""Fusion brouillon LLM + heuristique."""

import pytest

from app.schemas.invoice_pipeline import InvoiceExtractionDraft, InvoiceLineDraft
from app.services.invoice_draft_merge import merge_draft_with_heuristic


def test_merge_keeps_llm_supplier_fills_heuristic_total() -> None:
    llm = InvoiceExtractionDraft(
        supplier_name="SOCEP",
        invoice_number="FA005/2026",
        total_amount=None,
        items=[],
    )
    heur = InvoiceExtractionDraft(
        supplier_name="WRONG VENDOR",
        total_amount=15576.0,
        items=[
            InvoiceLineDraft(
                description="Poussin",
                quantity=8900.0,
                unit_price=1750.0,
                line_subtotal=15575000.0,
            )
        ],
    )
    m = merge_draft_with_heuristic(llm, heur)
    assert m.supplier_name == "SOCEP"
    assert m.invoice_number == "FA005/2026"
    assert m.total_amount == pytest.approx(15576.0)
    assert len(m.items) == 1


def test_merge_fills_empty_llm_from_heuristic() -> None:
    llm = InvoiceExtractionDraft()
    heur = InvoiceExtractionDraft(
        supplier_name="ACME",
        invoice_number="X-1",
        invoice_date="2026-01-16",
        total_amount=100.0,
    )
    m = merge_draft_with_heuristic(llm, heur)
    assert m.supplier_name == "ACME"
    assert m.invoice_number == "X-1"
    assert m.invoice_date == "2026-01-16"
