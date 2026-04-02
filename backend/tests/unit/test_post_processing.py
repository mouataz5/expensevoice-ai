"""Post-correction dates / mots OCR."""

from app.schemas.invoice_pipeline import InvoiceExtractionDraft, InvoiceLineDraft
from app.utils.post_processing import (
    fix_common_words,
    fix_invalid_date,
    post_correct_invoice_draft,
)


def test_fix_invalid_date_36_to_16() -> None:
    fixed, note = fix_invalid_date("36/01/2026")
    assert fixed == "2026-01-16"
    assert note and "36" in note and "16" in note


def test_fix_invalid_date_iso_bad_day() -> None:
    fixed, _ = fix_invalid_date("2026-01-36")
    assert fixed == "2026-01-16"


def test_fix_common_words_chat_to_chair_with_context() -> None:
    ocr = "Poussin chat 1750"
    t = fix_common_words("Poussin chat", ocr_context=ocr)
    assert "chair" in t.lower()
    assert "chat" not in t.lower()


def test_post_correct_draft_date_and_description() -> None:
    d = InvoiceExtractionDraft(
        invoice_date="36/01/2026",
        supplier_name="X",
        items=[InvoiceLineDraft(description="Poussin chat", quantity=1.0, unit_price=1.0, line_subtotal=1.0)],
    )
    out, journal = post_correct_invoice_draft(d, ocr_context="volaille")
    assert out.invoice_date == "2026-01-16"
    assert journal.get("dates")
    assert "chair" in (out.items[0].description or "").lower()
