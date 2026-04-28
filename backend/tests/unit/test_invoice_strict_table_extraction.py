"""Mode strict INVOICE_STRICT_TABLE_EXTRACTION : échec propre sans lignes factices."""
import asyncio

import pytest

from app.schemas.invoice_pipeline import InvoiceExtractionDraft, InvoiceLineDraft, OCRResult
from app.services.invoice_pipeline_core import complete_invoice_extraction_from_normalized
from app.services.invoice_table_strict import TABLE_EXTRACTION_FAILED


def test_strict_mode_fails_cleanly_without_structured_table_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVOICE_STRICT_TABLE_EXTRACTION", "1")

    async def fake_llm(_norm: str, _tt: str) -> tuple[InvoiceExtractionDraft, str]:
        return (
            InvoiceExtractionDraft(
                items=[
                    InvoiceLineDraft(
                        description="phantom",
                        quantity=1.0,
                        unit_price=1.0,
                        line_subtotal=1.0,
                    ),
                ],
                total_amount=999.0,
                subtotal_amount=900.0,
            ),
            "",
        )

    monkeypatch.setattr(
        "app.services.invoice_pipeline_core.extract_invoice_with_llm",
        fake_llm,
    )

    ocr = OCRResult(
        raw_text="FACTURE STE TEST\nArticle un 10 KG",
        metadata={"provider": "paddle", "structured_tables": []},
    )

    resp = asyncio.run(
        complete_invoice_extraction_from_normalized(
            raw_ocr=ocr.raw_text,
            normalized=ocr.raw_text,
            transaction_type="buy",
            ocr_for_confidence=ocr,
            debug=False,
        )
    )

    assert resp.success is False
    assert resp.extraction_status == "FAILED"
    assert resp.extraction_error_code == TABLE_EXTRACTION_FAILED
    assert not resp.data.items
    assert resp.data.subtotal_amount is None
    assert resp.data.tax_amount is None
    assert resp.data.total_amount is None
    assert resp.extraction_error_message
