"""Non-régression cas devis Abdouli (montants TN espaces, MF, TVA 19 %)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.invoice_extraction import heuristic_invoice_from_ocr
from app.services.invoice_pdf import generate_invoice_report_pdf
from app.utils.money import normalize_tunisian_amount

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "invoices"


def test_normalize_tunisian_amount_spaced_millimes():
    assert normalize_tunisian_amount("44 723.000") == pytest.approx(44723.0)
    assert normalize_tunisian_amount("8 407.070") == pytest.approx(8407.07)
    assert normalize_tunisian_amount("53 137.070") == pytest.approx(53137.07)


def test_abdouli_heuristic_supplier_client():
    text = (FIX / "abdouli_devis_ocr.txt").read_text(encoding="utf-8")
    h = heuristic_invoice_from_ocr(text, "buy")
    assert "Abdouli" in (h.get("supplier_name") or "")
    assert "volaille" in (h.get("client_name") or "").lower()
    assert h.get("supplier_tax_id") == "1044308Q"
    assert h.get("client_tax_id") == "1823117/X"
    assert h.get("supplier_phone") == "98.104.335"
    assert "Sidi" in (h.get("supplier_address") or "")


def test_abdouli_document_type_and_date():
    text = (FIX / "abdouli_devis_ocr.txt").read_text(encoding="utf-8")
    h = heuristic_invoice_from_ocr(text, "buy")
    assert h.get("document_type") == "quote"
    assert h.get("invoice_number") == "DV-2025-042"
    assert h.get("invoice_date") == "2025-12-22"


def test_abdouli_totals_and_currency():
    text = (FIX / "abdouli_devis_ocr.txt").read_text(encoding="utf-8")
    h = heuristic_invoice_from_ocr(text, "buy")
    assert h.get("currency") == "TND"
    assert h.get("subtotal_htva") == pytest.approx(44723.0)
    assert h.get("tax_amount") == pytest.approx(8407.07, rel=1e-4)
    assert h.get("total_ttc") == pytest.approx(53137.07, rel=1e-4)
    assert h.get("tax_rate_percent") == pytest.approx(19.0)


def test_abdouli_table_three_lines():
    text = (FIX / "abdouli_devis_ocr.txt").read_text(encoding="utf-8")
    h = heuristic_invoice_from_ocr(text, "buy")
    assert len(h.get("items") or []) == 3


def test_pdf_excludes_raw_ocr_blob(tmp_path: Path):
    secret = "XYZZY_OCR_SECRET_BLOB_12345"
    extracted = {
        "document_type": "quote",
        "supplier_name": "Test",
        "invoice_number": "X",
        "invoice_date": "2025-01-01",
        "currency": "TND",
        "items": [],
        "subtotal_htva": 0.0,
        "tax_amount": 0.0,
        "stamp_duty": 0.0,
        "total_ttc": 0.0,
        "totals": {"htva": 0.0, "tva": 0.0, "timbre": None, "ttc": 0.0},
        "normalized_text": secret,
        "user_warnings": [],
        "confidence": 0.5,
    }
    pdf_path = tmp_path / "rep.pdf"
    generate_invoice_report_pdf(extracted, "u@test.com", "2025-01-01T12:00:00", "buy", None, str(pdf_path))
    data = pdf_path.read_bytes()
    assert secret.encode() not in data
