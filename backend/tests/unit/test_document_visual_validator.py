"""Tests couche vision LLaVA/Ollama (fusion prudente, repli si indisponible)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest import mock

import httpx
import pytest

from app.schemas.invoice_pipeline import (
    InvoiceExtractionDraft,
    InvoiceLineDraft,
    InvoiceValidationResult,
    OCRResult,
)
from app.services.invoice_line_items_safety import apply_llava_visual_line_items_policy
from app.services.invoice_validation_service import validate_invoice_draft
from app.services.vision.document_visual_validator import (
    apply_llava_merge_to_pipeline_state,
    maybe_apply_ollama_llava_after_validation,
    should_run_llava_visual_validation,
)
from app.services.vision import ollama_llava_service as ollama_mod


def _ocr() -> OCRResult:
    return OCRResult(
        raw_text="FACTURE TOTAL TTC 1200 TND",
        confidence=0.5,
        metadata={"provider": "test"},
    )


def test_should_run_false_when_ollama_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OLLAMA_ENABLED", "0")
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    draft = InvoiceExtractionDraft(global_confidence=0.1)
    val = InvoiceValidationResult(global_confidence=0.1)
    assert not should_run_llava_visual_validation(
        str(img),
        draft=draft,
        validation=val,
        ocr=_ocr(),
        table_strict_failed=False,
        surya_applied=False,
    )


def test_should_run_true_on_table_strict_failed_when_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OLLAMA_ENABLED", "1")
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    draft = InvoiceExtractionDraft(global_confidence=0.9)
    val = InvoiceValidationResult(global_confidence=0.9, is_coherent_total=True)
    assert should_run_llava_visual_validation(
        str(img),
        draft=draft,
        validation=val,
        ocr=_ocr(),
        table_strict_failed=True,
        surya_applied=True,
    )


def test_classify_graceful_when_ollama_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OLLAMA_ENABLED", "0")
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    out = ollama_mod.classify_document_type(str(img))
    assert out.get("error") == "ollama_disabled"
    assert out.get("detected_type") == "unknown"


def test_ollama_chat_vision_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OLLAMA_ENABLED", "1")

    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {}

    def _boom(*_a, **_kw):
        raise httpx.TimeoutException("timeout")

    with mock.patch("httpx.Client.post", side_effect=_boom):
        content, err = ollama_mod.ollama_chat_vision(str(img), "ping")
    assert content is None
    assert err == "timeout"


def test_apply_merge_promotes_devis_and_drops_invoice_number_missing() -> None:
    draft = InvoiceExtractionDraft(
        document_type="invoice",
        supplier_name="ACME",
        invoice_date="2024-01-15",
        total_amount=500.0,
        subtotal_amount=431.0,
        tax_amount=69.0,
        stamp_tax=0.0,
        currency="TND",
        global_confidence=0.55,
    )
    raw = "DEVIS QUOTATION\nACME\nTotal TTC 500"
    val = validate_invoice_draft(draft, raw)
    ocr = OCRResult(raw_text=raw, confidence=0.88)
    audit = {
        "skipped": False,
        "audit": {
            "document": {"detected_type": "quote", "type_confidence": 0.92, "reasoning_short": "devis"},
            "headers": {},
            "totals": {},
            "review": {
                "manual_review_required": False,
                "confidence_delta": -0.02,
                "reason_codes": [],
                "summary_for_user": "",
            },
        },
    }
    d2, v2, pc = apply_llava_merge_to_pipeline_state(
        draft,
        val,
        {},
        audit,
        raw_ocr=raw,
        ocr=ocr,
    )
    assert d2.document_type == "quote"
    assert "invoice_number" not in (v2.missing_fields or [])


def test_apply_merge_strong_totals_ignore_harsh_negative_delta() -> None:
    draft = InvoiceExtractionDraft(
        document_type="invoice",
        supplier_name="ACME",
        invoice_number="F-99",
        invoice_date="2024-01-15",
        total_amount=500.0,
        subtotal_amount=431.0,
        tax_amount=69.0,
        stamp_tax=0.0,
        currency="TND",
        global_confidence=0.85,
    )
    raw = "FACTURE F-99"
    val = validate_invoice_draft(draft, raw)
    gc_before = float(val.global_confidence or 0.0)
    ocr = OCRResult(raw_text=raw + " x" * 400, confidence=0.9)
    audit = {
        "skipped": False,
        "audit": {
            "document": {"detected_type": "invoice", "type_confidence": 0.5, "reasoning_short": ""},
            "headers": {},
            "totals": {},
            "review": {
                "manual_review_required": False,
                "confidence_delta": -0.15,
                "reason_codes": [],
                "summary_for_user": "",
            },
        },
    }
    d2, v2, _pc = apply_llava_merge_to_pipeline_state(
        draft,
        val,
        {},
        audit,
        raw_ocr=raw,
        ocr=ocr,
    )
    assert d2.total_amount == 500.0
    assert float(v2.global_confidence or 0) >= gc_before - 1e-6


def test_apply_merge_manual_review_does_not_change_totals() -> None:
    draft = InvoiceExtractionDraft(
        document_type="invoice",
        supplier_name="ACME",
        total_amount=200.0,
        currency="TND",
        items=[InvoiceLineDraft(description="A", quantity=1, unit_price=200, line_subtotal=200)],
        global_confidence=0.5,
    )
    raw = "x"
    val = validate_invoice_draft(draft, raw)
    ocr = _ocr()
    audit = {
        "skipped": False,
        "audit": {
            "document": {"detected_type": "unknown", "type_confidence": 0.2, "reasoning_short": ""},
            "headers": {},
            "totals": {},
            "review": {
                "manual_review_required": True,
                "confidence_delta": 0.0,
                "reason_codes": ["table_unreadable"],
                "summary_for_user": "Relecture conseillée.",
            },
        },
    }
    d2, _v2, pc = apply_llava_merge_to_pipeline_state(
        draft,
        val,
        {},
        audit,
        raw_ocr=raw,
        ocr=ocr,
    )
    assert d2.total_amount == 200.0
    assert pc["llava_visual"].get("manual_review_required") is True
    assert "Relecture conseillée." in (d2.warnings or [])


def test_maybe_apply_noop_when_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OLLAMA_ENABLED", "0")
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    draft = InvoiceExtractionDraft(global_confidence=0.1)
    val = InvoiceValidationResult(global_confidence=0.1)
    pc_in = {"a": 1}

    async def _run():
        return await maybe_apply_ollama_llava_after_validation(
            image_path=str(img),
            draft=draft,
            validation=val,
            post_corrections=pc_in,
            raw_ocr="test",
            ocr=_ocr(),
            table_strict_failed=True,
            surya_applied=False,
        )

    d2, v2, pc_out = asyncio.run(_run())
    assert d2 is draft and v2 is val and pc_out == pc_in


def test_apply_llava_line_items_policy_suppresses_rows() -> None:
    stored = {
        "extraction": {
            "items": [{"description": "x", "quantity": 1, "unit_price": 1, "line_subtotal": 1}],
            "document_type": "invoice",
        },
        "items": [{"line_subtotal": 1}],
        "validation": {"warnings": [], "validation_flags": []},
        "warnings": [],
        "pipeline": {
            "post_corrections": {
                "llava_visual": {
                    "skipped": False,
                    "manual_review_required": True,
                    "summary_for_user": "Vue floue.",
                }
            }
        },
    }
    out = apply_llava_visual_line_items_policy(stored)
    assert out["line_items_trust"] == "manual_review_required"
    assert (out.get("extraction") or {}).get("items") == []
    assert out.get("items") == []


def test_llava_skipped_merge_leaves_post_corrections_minimal() -> None:
    draft = InvoiceExtractionDraft(global_confidence=0.5)
    val = InvoiceValidationResult(global_confidence=0.5)
    ocr = _ocr()
    d2, v2, pc = apply_llava_merge_to_pipeline_state(
        draft,
        val,
        {"x": 1},
        {"skipped": True, "error": "timeout"},
        raw_ocr="",
        ocr=ocr,
    )
    assert d2 is draft
    assert v2 is val
    assert pc["llava_visual"]["skipped"] is True
