"""Validation métier sur drafts factures."""
import pytest

from app.schemas.invoice_pipeline import InvoiceExtractionDraft, InvoiceLineDraft
from app.services.invoice_validation_service import validate_invoice_draft


def test_totals_coherent_sub_tax_stamp() -> None:
    d = InvoiceExtractionDraft(
        subtotal_amount=100.0,
        tax_amount=19.0,
        stamp_tax=1.0,
        total_amount=120.0,
        currency="TND",
        supplier_name="X",
        invoice_number="1",
        invoice_date="2026-01-01",
    )
    v = validate_invoice_draft(d, "TND")
    assert v.is_coherent_total is True


def test_line_incoherent_qty_unit() -> None:
    d = InvoiceExtractionDraft(
        items=[
            InvoiceLineDraft(quantity=2.0, unit_price=10.0, line_subtotal=999.0, description="A"),
        ]
    )
    v = validate_invoice_draft(d, "")
    assert v.is_coherent_lines is False
    assert any("Ligne" in w for w in v.warnings)


def test_likely_paid_in_full() -> None:
    d = InvoiceExtractionDraft(
        total_amount=100.0,
        amount_paid=100.0,
        remaining_due=0.0,
        currency="TND",
        supplier_name="S",
        invoice_number="N",
        invoice_date="2026-01-01",
    )
    v = validate_invoice_draft(d, "")
    assert v.likely_paid_in_full is True


def test_currency_hint_from_ocr() -> None:
    d = InvoiceExtractionDraft(supplier_name="A", invoice_number="1", invoice_date="2026-01-01", total_amount=1.0)
    v = validate_invoice_draft(d, "Montant 100 TND")
    assert v.validation_flags
    assert any(f.code == "currency_inferred" for f in v.validation_flags)

