"""
Golden OCR text fixtures — validates heuristic extraction (no LLM / no image binaries).
"""
from pathlib import Path

import pytest

from app.services.invoice_extraction import (
    _parse_amount_token,
    _sanitize_supplier_name,
    heuristic_invoice_from_ocr,
    merge_heuristic_into_extracted,
    reconcile_extracted_invoice_numbers,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "invoices"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_amount_space_thousands() -> None:
    assert _parse_amount_token("5 810,000") == pytest.approx(5810.0)
    assert _parse_amount_token("22 176,003") == pytest.approx(22176.003)
    assert _parse_amount_token("15.575,000") == pytest.approx(15575.0)


def test_socep_buy_supplier_and_total() -> None:
    text = _load("socep_ocr.txt")
    h = heuristic_invoice_from_ocr(text, "buy")
    assert "SOCEP" in (h.get("supplier_name") or "").upper()
    assert "ABBES" not in (h.get("supplier_name") or "").upper() or "CENTRE" in (
        h.get("supplier_name") or ""
    ).upper()
    assert h.get("total_ttc", 0) == pytest.approx(15576.0, rel=0, abs=1.0)
    assert len(h.get("items") or []) >= 1


def test_stpa_buy_multi_line_and_ttc() -> None:
    text = _load("stpa_ocr.txt")
    h = heuristic_invoice_from_ocr(text, "buy")
    assert "STPA" in (h.get("supplier_name") or "").upper() or "TUNISIENNE" in (
        h.get("supplier_name") or ""
    ).upper()
    assert h.get("total_ttc", 0) == pytest.approx(22176.003, rel=0, abs=2.0)
    assert len(h.get("items") or []) >= 2


def test_acn_buy_net_payer() -> None:
    text = _load("acn_ocr.txt")
    h = heuristic_invoice_from_ocr(text, "buy")
    assert "ACN" in (h.get("supplier_name") or "").upper() or "ALIMENTS" in (
        h.get("supplier_name") or ""
    ).upper()
    assert h.get("total_ttc", 0) == pytest.approx(5874.16, rel=0, abs=1.0)


def test_tahar_buy() -> None:
    text = _load("tahar_ocr.txt")
    h = heuristic_invoice_from_ocr(text, "buy")
    assert "TAHAR" in (h.get("supplier_name") or "").upper() or "TLILI" in (
        h.get("supplier_name") or ""
    ).upper()
    assert h.get("total_ttc", 0) == pytest.approx(2198.5, rel=0, abs=1.0)


def test_medimix_buy() -> None:
    text = _load("medimix_ocr.txt")
    h = heuristic_invoice_from_ocr(text, "buy")
    assert "MEDIMIX" in (h.get("supplier_name") or "").upper()
    assert h.get("total_ttc", 0) == pytest.approx(11748.792, rel=0, abs=2.0)
    assert len(h.get("items") or []) >= 2


def test_socep_timbre_separate_from_tva() -> None:
    text = _load("socep_ocr.txt")
    h = heuristic_invoice_from_ocr(text, "buy")
    assert float(h.get("stamp_duty") or 0) == pytest.approx(1.0, abs=0.2)
    assert float(h.get("tax_amount") or 0) == pytest.approx(0.0, abs=0.01)


def test_sanitize_supplier_trailing_garbage() -> None:
    raw = "STE DE CENTRE DES POUSSINS Puis ins Bip autres"
    assert "Puis" not in _sanitize_supplier_name(raw)
    assert "POUSSINS" in _sanitize_supplier_name(raw).upper()


def test_reconcile_clamps_insane_ttc_vs_line_items() -> None:
    ex = {
        "supplier_name": "X",
        "items": [
            {
                "designation": "Poussin",
                "quantity": 8900,
                "unit_price": 1750,
                "line_total": 15575000.0,
            }
        ],
        "subtotal_htva": 0.0,
        "tax_amount": 1.0,
        "stamp_duty": 0.0,
        "total_ttc": 5080101.0,
        "currency": "TND",
    }
    out = reconcile_extracted_invoice_numbers(
        ex, ocr_text="dummy", transaction_type="buy"
    )
    assert float(out["total_ttc"]) == pytest.approx(15575001.0, rel=0, abs=5.0)
    assert float(out["subtotal_htva"]) == pytest.approx(15575000.0, rel=0, abs=1.0)


def test_ste_abbes_buy_multiline_line_and_totals() -> None:
    """Own-invoice layout: STE ABBES header; qty/PU/total on next line after label."""
    text = _load("ste_abbes_header_ocr.txt")
    h = heuristic_invoice_from_ocr(text, "buy")
    assert "ABBES" in (h.get("supplier_name") or "").upper()
    assert h.get("total_ttc", 0) == pytest.approx(15576.0, rel=0, abs=2.0)
    assert len(h.get("items") or []) >= 1


def test_merge_replaces_ste_abbes_with_issuer_when_llm_wrong() -> None:
    text = _load("socep_ocr.txt")
    bad_llm = {
        "supplier_name": "STE ABBES POUR VOLAILLE",
        "items": [],
        "total_ttc": 0.0,
        "currency": "TND",
    }
    merged = merge_heuristic_into_extracted(bad_llm, text, "buy")
    assert "SOCEP" in (merged.get("supplier_name") or "").upper()
    assert merged.get("total_ttc", 0) > 1000


def test_sell_prefers_client() -> None:
    text = _load("stpa_ocr.txt")
    h = heuristic_invoice_from_ocr(text, "sell")
    assert "ABBES" in (h.get("supplier_name") or "").upper()
