"""Extraction structurée tables Surya (métadonnées simulées)."""
from __future__ import annotations

from app.services.invoice_facades.surya_table_extractor import (
    detect_table_columns,
    extract_invoice_lines_from_surya_metadata,
    parse_surya_table_rows,
    validate_and_correct_rows,
)


def _tn_table() -> dict:
    return {
        "table_idx": 0,
        "cells": [
            # header
            {"row_id": 0, "col_id": 0, "text": "Désignation", "is_header": True, "bbox": [10, 10, 100, 30]},
            {"row_id": 0, "col_id": 1, "text": "UNITE", "is_header": True, "bbox": [110, 10, 150, 30]},
            {"row_id": 0, "col_id": 2, "text": "QTE", "is_header": True, "bbox": [160, 10, 200, 30]},
            {"row_id": 0, "col_id": 3, "text": "P.U", "is_header": True, "bbox": [210, 10, 280, 30]},
            {"row_id": 0, "col_id": 4, "text": "P.HT", "is_header": True, "bbox": [290, 10, 380, 30]},
            # data
            {"row_id": 1, "col_id": 0, "text": "Engrais NPK", "bbox": [10, 40, 100, 60]},
            {"row_id": 1, "col_id": 1, "text": "SAC", "bbox": [110, 40, 150, 60]},
            {"row_id": 1, "col_id": 2, "text": "10", "bbox": [160, 40, 200, 60]},
            {"row_id": 1, "col_id": 3, "text": "25,500", "bbox": [210, 40, 280, 60]},
            {"row_id": 1, "col_id": 4, "text": "255,000", "bbox": [290, 40, 380, 60]},
        ],
    }


def test_detect_table_columns_roles():
    t = _tn_table()
    info = detect_table_columns(t)
    roles = {int(k): v for k, v in info["col_roles"].items()}
    assert roles.get(0) == "designation"
    assert roles.get(1) == "unit"
    assert roles.get(2) == "quantity"
    assert roles.get(3) == "unit_price"
    assert roles.get(4) == "line_ht"


def test_parse_and_validate_rows():
    t = _tn_table()
    info = detect_table_columns(t)
    rows, _j = parse_surya_table_rows(t, column_info=info)
    assert len(rows) == 1
    assert rows[0].description == "Engrais NPK"
    assert rows[0].quantity == 10
    assert rows[0].unit == "SAC"
    fixed, _corr = validate_and_correct_rows(rows)
    assert fixed[0].line_ht is not None
    assert fixed[0].unit_price is not None


def test_extract_from_metadata_applies():
    meta = {
        "provider": "surya",
        "surya_tables": [_tn_table()],
    }
    lines, dbg = extract_invoice_lines_from_surya_metadata(meta)
    assert dbg.get("applied_to_draft") is True
    assert len(lines) == 1
    assert lines[0].description == "Engrais NPK"
    assert lines[0].quantity == 10.0


def test_non_surya_provider_skips():
    lines, dbg = extract_invoice_lines_from_surya_metadata({"provider": "paddleocr"})
    assert lines == []
    assert dbg.get("applied_to_draft") is False
