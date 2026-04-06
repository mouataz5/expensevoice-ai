"""Corrections heuristiques des zéros LLM sur lignes / totaux."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.invoice_pipeline import InvoiceExtractionDraft, InvoiceLineDraft
from app.services.invoice_heuristics import detect_line_items_from_text, detect_totals, fix_zero_values

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "invoices"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_detect_line_items_socep() -> None:
    text = _load("socep_ocr.txt")
    rows = detect_line_items_from_text(text)
    assert len(rows) >= 1
    assert rows[0].get("quantity", 0) > 0
    assert rows[0].get("line_total", 0) > 0


def test_detect_totals_socep() -> None:
    text = _load("socep_ocr.txt")
    t = detect_totals(text)
    assert (t.get("total_ttc") or 0) > 1000


def test_fix_zero_values_restores_from_ocr() -> None:
    text = _load("socep_ocr.txt")
    bad = InvoiceExtractionDraft(
        items=[
            InvoiceLineDraft(
                description="ALIMENT COMPOSE",
                quantity=0.0,
                unit_price=0.0,
                line_subtotal=0.0,
            )
        ],
        total_amount=0.0,
        currency="TND",
    )
    fixed, journal = fix_zero_values(bad, text, "buy")
    assert fixed.items
    assert (fixed.items[0].quantity or 0) > 0 or (fixed.items[0].line_subtotal or 0) > 0
    assert (fixed.total_amount or 0) > 1000
    assert journal.get("line_fixes") or journal.get("totals_fixes") or journal.get("replaced_items")


def test_fix_zero_replaces_all_when_only_zeros() -> None:
    text = _load("stpa_ocr.txt")
    bad = InvoiceExtractionDraft(
        items=[
            InvoiceLineDraft(description="X", quantity=0, unit_price=0, line_subtotal=0),
            InvoiceLineDraft(description="Y", quantity=0, unit_price=0, line_subtotal=0),
        ],
        total_amount=0.0,
    )
    fixed, journal = fix_zero_values(bad, text, "buy")
    assert journal.get("replaced_items") is True
    assert len(fixed.items) >= 2
    usable = sum(
        1
        for it in fixed.items
        if (it.line_subtotal or 0) > 0 and (it.quantity or 0) > 0 and (it.unit_price or 0) > 0
    )
    assert usable >= 1
