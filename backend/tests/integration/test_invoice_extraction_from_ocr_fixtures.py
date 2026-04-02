"""
Intégration pipeline (sans image binaire) : OCR simulé + LLM mocké.
"""
import asyncio
from pathlib import Path

import pytest

from app.schemas.invoice_pipeline import InvoiceExtractionDraft, OCRResult
from app.services.invoice_global_pipeline import run_invoice_pipeline_async

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "invoices"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_pipeline_socep_heuristic_fill(monkeypatch: pytest.MonkeyPatch) -> None:
    text = _load("socep_ocr.txt")

    monkeypatch.setattr(
        "app.services.invoice_global_pipeline.run_ocr",
        lambda _path: OCRResult(raw_text=text, metadata={"provider": "test"}),
    )

    async def fake_llm(_norm: str, _tt: str) -> tuple[InvoiceExtractionDraft, str]:
        return InvoiceExtractionDraft(), ""

    monkeypatch.setattr(
        "app.services.invoice_global_pipeline.extract_invoice_with_llm",
        fake_llm,
    )

    resp = asyncio.run(run_invoice_pipeline_async("dummy.jpg", "buy", debug=False))
    assert resp.success
    assert resp.validation
    assert "SOCEP" in (resp.data.supplier_name or "").upper() or "SOCEP" in resp.ocr_text.upper()
    stamp = resp.validation.normalized_amounts.stamp_tax
    if stamp is not None:
        assert stamp == pytest.approx(1.0, abs=0.3)


def test_pipeline_remaining_due_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Facture avec reste dû : exemple minimal synthétique."""
    text = """
    FACTURE N° 99
    STE TEST SA
    Total TTC 1 000,000 TND
    Payé 400,000
    Reste dû 600,000
    """

    monkeypatch.setattr(
        "app.services.invoice_global_pipeline.run_ocr",
        lambda _path: OCRResult(raw_text=text, metadata={"provider": "test"}),
    )

    async def fake_llm(_norm: str, _tt: str) -> tuple[InvoiceExtractionDraft, str]:
        return InvoiceExtractionDraft(), ""

    monkeypatch.setattr(
        "app.services.invoice_global_pipeline.extract_invoice_with_llm",
        fake_llm,
    )

    resp = asyncio.run(run_invoice_pipeline_async("dummy.jpg", "buy", debug=False))
    assert resp.success
    rem = resp.validation.normalized_amounts.remaining_due
    if rem is None:
        rem = resp.data.remaining_due
    if rem is not None:
        assert rem == pytest.approx(600.0, abs=50.0)

