"""Corrections colonnes qté / prix sur grilles Surya synthétiques."""
from __future__ import annotations

from app.services.invoice_facades.surya_table_extractor import (
    TableRowModel,
    _maybe_swap_qty_unit_price,
    validate_and_correct_rows,
)


def test_swap_qty_price_when_product_matches_swapped():
    r = TableRowModel(
        description="Poussin",
        unit="UN",
        quantity=6590.0,
        unit_price=1.0,
        line_ht=6590.0,
        line_ttc=None,
        source_row_id=3,
    )
    fixed, note = _maybe_swap_qty_unit_price(r)
    assert note == "swapped_qty_unit_price"
    assert fixed.quantity == 1.0
    assert fixed.unit_price == 6590.0


def test_validate_rows_keeps_ht_after_swap():
    rows = [
        TableRowModel(
            description="Item A",
            unit="UN",
            quantity=100.0,
            unit_price=2.0,
            line_ht=200.0,
            line_ttc=None,
            source_row_id=1,
        )
    ]
    out, journal = validate_and_correct_rows(rows)
    assert out[0].quantity == 100.0
    assert "swapped" not in " ".join(journal)


def test_row_remap_clustering_preserves_parse(monkeypatch):
    from app.services.invoice_facades import surya_table_extractor as ste

    table = {
        "cells": [
            {"row_id": 0, "col_id": 0, "text": "Désignation", "bbox": [10, 10, 100, 22], "is_header": True},
            {"row_id": 2, "col_id": 0, "text": "Produit", "bbox": [10, 40, 100, 52], "is_header": False},
            {"row_id": 2, "col_id": 3, "text": "1", "bbox": [200, 40, 220, 52], "is_header": False},
            {"row_id": 2, "col_id": 4, "text": "1825", "bbox": [250, 40, 290, 52], "is_header": False},
            {"row_id": 2, "col_id": 5, "text": "1 825,000", "bbox": [300, 40, 370, 52], "is_header": False},
        ]
    }
    cells = ste._normalize_cells(table)
    assert len({c["row_id"] for c in cells}) <= 3
