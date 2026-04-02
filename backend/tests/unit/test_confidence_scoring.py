"""Scoring de confiance facture."""

from app.schemas.invoice_pipeline import (
    InvoiceExtractionDraft,
    InvoiceLineDraft,
    InvoiceValidationResult,
    OCRResult,
)
from app.services.confidence_scoring import (
    compute_global_confidence,
    draft_field_coverage,
    ocr_quality_from_result,
)


def test_ocr_quality_saturates_for_typical_invoice_text() -> None:
    text = "FACTURE N° FA1/2026\nSTE TEST\nTOTAL TTC 1.500,000 TND\nSOUS-TOTAL 1.000\n" * 8
    ocr = OCRResult(raw_text=text, confidence=0.88)
    q = ocr_quality_from_result(ocr)
    assert q >= 0.72


def test_field_coverage_bonus_client_and_subtotal() -> None:
    sparse = InvoiceExtractionDraft(
        supplier_name="X",
        invoice_number="1",
        invoice_date="2026-01-01",
        total_amount=100.0,
        currency="TND",
        items=[],
    )
    c0 = draft_field_coverage(sparse)
    c1 = draft_field_coverage(
        sparse.model_copy(
            update={
                "client_name": "CLIENT SA",
                "subtotal_amount": 100.0,
                "stamp_tax": 1.0,
                "items": [
                    InvoiceLineDraft(
                        description="a", quantity=1.0, unit_price=100.0, line_subtotal=100.0
                    )
                ],
            }
        )
    )
    assert c1 > c0


def test_global_confidence_higher_when_coherent_and_complete() -> None:
    ocr = OCRResult(
        raw_text="FACTURE FA/1\nSTE A\nTOTAL 100 TND\nDATE 01/01/2026\n" * 5,
        confidence=0.9,
    )
    draft = InvoiceExtractionDraft(
        supplier_name="STE A",
        invoice_number="FA/1",
        invoice_date="2026-01-01",
        total_amount=100.0,
        currency="TND",
        global_confidence=0.7,
        items=[InvoiceLineDraft(description="p", quantity=2.0, unit_price=50.0, line_subtotal=100.0)],
    )
    val_ok = InvoiceValidationResult(
        is_coherent_total=True,
        is_coherent_lines=True,
        missing_fields=[],
    )
    val_bad = InvoiceValidationResult(
        is_coherent_total=False,
        is_coherent_lines=False,
        missing_fields=["supplier_name", "total_amount"],
    )
    _, g_ok = compute_global_confidence(ocr, draft, val_ok)
    _, g_bad = compute_global_confidence(ocr, draft, val_bad)
    assert g_ok > g_bad
    assert g_ok >= 0.55
