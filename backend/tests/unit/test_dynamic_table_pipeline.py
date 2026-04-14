"""Flux dynamique tableau : revue basse → lignes vides pour le brouillon."""
from __future__ import annotations

from unittest.mock import patch

from app.schemas.invoice_pipeline import InvoiceLineDraft, OCRResult
from app.services.table_understanding.dynamic_table_pipeline import run_dynamic_table_understanding


def test_run_dynamic_table_understanding_low_status_clears_trusted_lines() -> None:
    fake_lines = [
        InvoiceLineDraft(description="X", quantity=1.0, unit_price=10.0, line_subtotal=10.0),
    ]
    fake_dbg = {
        "applied_to_draft": True,
        "reason": "ok",
        "line_count": 1,
        "table_correction": {
            "manual_review_required": True,
            "global_validation": {
                "global_ok": False,
                "line_math_ok": False,
                "subtotal_ok": False,
                "total_formula_ok": False,
                "incoherent_rows": 5,
            },
            "rows": [{"confidence": 0.2, "auto_repaired": False, "source_row_id": 0}],
        },
    }

    with patch(
        "app.services.table_understanding.dynamic_table_pipeline.extract_invoice_lines_from_surya_metadata",
        return_value=(fake_lines, fake_dbg),
    ):
        ocr = OCRResult(
            raw_text="x",
            metadata={"provider": "surya", "surya_tables": [{"cells": [{"text": "a"}]}]},
        )
        out = run_dynamic_table_understanding(ocr, document_hints={})

    assert out["candidate_lines"] == fake_lines
    assert out["lines"] == []
    assert out["review"]["extraction_status"] == "low"
    assert out["surya_debug"].get("applied_to_draft") is False


def test_run_dynamic_table_understanding_high_keeps_lines() -> None:
    fake_lines = [
        InvoiceLineDraft(description="A", quantity=2.0, unit_price=5.0, line_subtotal=10.0),
    ]
    fake_dbg = {
        "applied_to_draft": True,
        "reason": "ok",
        "table_correction": {
            "manual_review_required": False,
            "global_validation": {
                "global_ok": True,
                "line_math_ok": True,
                "subtotal_ok": True,
                "total_formula_ok": True,
                "incoherent_rows": 0,
            },
            "rows": [{"confidence": 0.9, "auto_repaired": True, "source_row_id": 0}],
        },
    }

    with patch(
        "app.services.table_understanding.dynamic_table_pipeline.extract_invoice_lines_from_surya_metadata",
        return_value=(fake_lines, fake_dbg),
    ):
        ocr = OCRResult(raw_text="x", metadata={"provider": "surya"})
        out = run_dynamic_table_understanding(ocr, {})

    assert len(out["lines"]) == 1
    assert out["review"]["extraction_status"] == "high"
