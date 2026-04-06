"""Tests parser tableau OCR (paires ligne + chiffres, TND, devise, validation)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import invoice_extraction
from app.services.invoice_table_parser import (
    detect_currency,
    detect_invoice_table_lines,
    detect_invoice_table_lines_debug,
    extract_totals_from_text,
    fix_line_item,
    merge_parser_line_items,
    normalize_tnd_amount,
    parse_line_numbers,
    validate_financials,
)

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "invoices"


def test_normalize_tnd_amount_triple_dot():
    assert normalize_tnd_amount("12.045.000") == pytest.approx(12045.0)
    assert normalize_tnd_amount("1.000") == pytest.approx(1.0)


def test_parse_line_numbers_sorted_triplet():
    p = parse_line_numbers([1825.0, 6600.0, 12045.0])
    assert p is not None
    assert p["unit_price"] == 1825.0
    assert p["quantity"] == 6600.0
    assert p["line_subtotal"] == 12045.0
    assert p["mapping"] == "sorted_triplet"


def test_detect_currency_tnd():
    assert detect_currency("SOUS-TOTAL 12.045.000 TND") == "TND"
    assert detect_currency("Rien que du français") == "TND"


def test_detect_invoice_table_lines_socep_split():
    text = (FIX / "socep_user_case_ocr.txt").read_text(encoding="utf-8")
    rows = detect_invoice_table_lines(text)
    assert len(rows) >= 1
    r = rows[0]
    assert "Poussin" in r["description"]
    assert len(r["raw_numbers"]) >= 3


def test_line_items_merge_prefers_short_designation():
    raw = (FIX / "socep_user_case_ocr.txt").read_text(encoding="utf-8")
    glued = invoice_extraction._glue_split_numeric_followups(raw)
    long_items = invoice_extraction._heur_find_line_items(glued)
    merged = merge_parser_line_items(raw, glued, long_items)
    assert len(merged) == 1
    assert merged[0]["quantity"] == pytest.approx(6600.0)
    assert merged[0]["unit_price"] == pytest.approx(1.825)
    assert merged[0]["line_total"] == pytest.approx(12045.0, rel=1e-4)
    des = merged[0]["designation"].lower()
    assert "poussin chair" in des
    assert len(merged[0]["designation"]) < len(long_items[0]["designation"])


def test_extract_totals_from_text_socep():
    text = (FIX / "socep_user_case_ocr.txt").read_text(encoding="utf-8")
    t = extract_totals_from_text(text)
    assert t.get("total_ttc") == pytest.approx(12046.0)
    assert t.get("stamp_duty") == pytest.approx(1.0)


def test_validate_financials_flags():
    inv = {
        "items": [{"line_total": 12045.0}],
        "subtotal_htva": 12045.0,
        "tax_amount": 0,
        "stamp_duty": 1.0,
        "total_ttc": 12046.0,
        "currency": "TND",
    }
    v = validate_financials(inv)
    assert v["flags"].get("lines_match_subtotal") is True
    assert v["flags"].get("total_consistent") is True


def test_fix_line_item_enrich_short():
    item = fix_line_item(
        {"designation": "Ate", "quantity": 1.0, "unit_price": 2.0, "line_total": 2.0},
        ocr_text="volaille poussin chair",
        neighbor_descriptions=["Poussin chair"],
    )
    assert "poussin" in item["designation"].lower()


def test_debug_structure():
    text = (FIX / "socep_ocr.txt").read_text(encoding="utf-8")
    d = detect_invoice_table_lines_debug(text)
    assert "bounds" in d and "rows" in d and "trace" in d
