"""Parsing Surya : colonnes par bbox (en-tête), col_id volontairement faux."""
from __future__ import annotations

import pytest

from app.services.invoice_facades.surya_table_extractor import parse_surya_table_rows, validate_and_correct_rows


def _cell(row: int, col_wrong: int, text: str, x0: float, x1: float, y0: float = 0.0, y1: float = 12.0) -> dict:
    return {
        "row_id": row,
        "col_id": col_wrong,
        "text": text,
        "bbox": [x0, y0, x1, y1],
        "is_header": row == 0,
    }


def test_geometry_parse_overrides_shuffled_col_ids() -> None:
    table = {
        "cells": [
            _cell(0, 99, "Désignation", 0, 120),
            _cell(0, 1, "UN", 125, 145),
            _cell(0, 0, "QTE", 150, 175),
            _cell(0, 3, "P.U", 180, 220),
            _cell(0, 2, "P.HT", 225, 280),
            # Ligne 1 : col_id ne correspond pas à la position X
            _cell(1, 9, "Article test", 5, 110),
            _cell(1, 0, "U", 128, 142),
            _cell(1, 5, "3", 158, 170),
            _cell(1, 1, "8229.000", 185, 250),
            _cell(1, 2, "24687.000", 230, 295),
        ]
    }
    rows, journal = parse_surya_table_rows(table, column_info=None)
    assert "parse_mode_geometry_bboxes" in journal
    fixed, _ = validate_and_correct_rows(rows)
    assert len(fixed) >= 1
    r0 = fixed[0]
    assert r0.quantity == pytest.approx(3)
    assert r0.unit_price == pytest.approx(8229.0)
    assert r0.line_ht == pytest.approx(24687.0)
