"""Non-régression cas SOCEP / STE ABBES (pipeline hybride + heuristique)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.invoice_pipeline import InvoiceExtractionDraft
from app.services.invoice_draft_merge import merge_llm_and_heuristic_invoice
from app.services.invoice_llm_extract import heuristic_to_global_draft
from app.services.invoice_heuristics import build_heuristic_invoice_dict
from app.utils.money import normalize_tunisian_invoice_amount

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "invoices" / "socep_user_case_ocr.txt"


def _text() -> str:
    return FIX.read_text(encoding="utf-8")


def test_normalize_tunisian_amounts() -> None:
    assert normalize_tunisian_invoice_amount("12.045.000") == pytest.approx(12045.0)
    assert normalize_tunisian_invoice_amount("1.000") == pytest.approx(1.0)
    assert normalize_tunisian_invoice_amount("12 045,000") == pytest.approx(12045.0)


def test_heuristic_invoice_number_client_stamp_total() -> None:
    h = build_heuristic_invoice_dict(_text(), "buy")
    assert (h.get("invoice_number") or "").upper() == "FA115/2025"
    assert "ABBES" in (h.get("client_name") or "").upper()
    assert "1823117" in (h.get("client_tax_id") or "")
    assert "SIDI" in (h.get("client_city") or "").upper() or (h.get("client_city") or "")
    assert float(h.get("stamp_duty") or 0) == pytest.approx(1.0, abs=0.05)
    assert float(h.get("total_ttc") or 0) == pytest.approx(12046.0, abs=0.5)
    rem = h.get("remaining_due")
    assert rem is None or float(rem) == pytest.approx(0.0, abs=0.01)


def test_heuristic_line_item_qty_pu_total() -> None:
    h = build_heuristic_invoice_dict(_text(), "buy")
    items = h.get("items") or []
    assert len(items) >= 1
    it = items[0]
    assert float(it.get("quantity") or 0) == pytest.approx(6600.0, rel=0, abs=2.0)
    # OCR « 1825 » souvent lu comme PU en millimes → 1.825 TND × qty = sous-total
    assert float(it.get("unit_price") or 0) == pytest.approx(1.825, rel=0, abs=0.05)
    assert float(it.get("line_total") or 0) == pytest.approx(12045.0, rel=0, abs=0.5)


def test_merge_llm_empty_invoice_number_uses_ocr() -> None:
    ocr = _text()
    llm = InvoiceExtractionDraft(invoice_number="", invoice_date="2025-12-05")
    heur = heuristic_to_global_draft(build_heuristic_invoice_dict(ocr, "buy"))
    merged, prov = merge_llm_and_heuristic_invoice(llm, heur, ocr)
    assert (merged.invoice_number or "").upper() == "FA115/2025"
    assert prov.get("invoice_number") in ("ocr_regex", "heuristic_agrees_ocr")
