"""Extraction structurée tables Surya (métadonnées simulées)."""
from __future__ import annotations

import pytest

from app.services.invoice_facades.surya_table_extractor import (
    TableRowModel,
    detect_table_columns,
    extract_invoice_lines_from_surya_metadata,
    parse_surya_table_rows,
    validate_and_correct_rows,
    _parse_quantity_cell,
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
    tc = dbg.get("table_correction") or {}
    assert "manual_review_required" in tc
    assert "global_validation" in tc


def test_non_surya_provider_skips():
    lines, dbg = extract_invoice_lines_from_surya_metadata({"provider": "paddleocr"})
    assert lines == []
    assert dbg.get("applied_to_draft") is False


def _devis_six_col_table() -> dict:
    """Grille type devis TN : Désignation, UN, QTE, P.U, P.H.T, P.T.T.C (3 lignes + en-tête)."""
    yh, h = 10, 22
    dy = 28

    def row_boxes(r: int) -> tuple[int, int]:
        y0 = yh + h + (r - 1) * dy
        return y0, y0 + h

    cells: list[dict] = []
    xcols = [
        (0, 10, 118),
        (1, 120, 158),
        (2, 160, 198),
        (3, 200, 268),
        (4, 270, 348),
        (5, 350, 438),
    ]
    headers = [
        "Désignation",
        "UNITE",
        "QTE",
        "P.U",
        "P.H.T",
        "P.T.T.C",
    ]
    for col_id, x0, x1 in xcols:
        cells.append(
            {
                "row_id": 0,
                "col_id": col_id,
                "text": headers[col_id],
                "is_header": True,
                "bbox": [x0, yh, x1, yh + h],
            }
        )
    rows_data = [
        ("Transfo mono 50 kVA", "UN", "3", "8 229.000", "24 687.000", "29 377.530"),
        ("Interrupteur", "UN", "1", "500.000", "500.000", "595.000"),
        ("Câble 4G", "UN", "2", "100.000", "200.000", "238.000"),
    ]
    for ri, texts in enumerate(rows_data, start=1):
        y0, y1 = row_boxes(ri)
        for col_id, x0, x1 in xcols:
            cells.append(
                {
                    "row_id": ri,
                    "col_id": col_id,
                    "text": texts[col_id],
                    "bbox": [x0, y0, x1, y1],
                }
            )
    return {"table_idx": 0, "cells": cells}


def _mini_totals_two_col_table() -> dict:
    """Bloc type « Total H.T / TVA / TTC » sans colonne désignation (2 colonnes)."""
    cells = []
    for ri, (a, b) in enumerate(
        [
            ("Total H.T", "25 387.000"),
            ("TVA 19%", "4 823.530"),
            ("Total TTC", "30 210.530"),
        ]
    ):
        y0, y1 = 400 + ri * 24, 418 + ri * 24
        cells.extend(
            [
                {"row_id": ri, "col_id": 0, "text": a, "bbox": [400, y0, 480, y1]},
                {"row_id": ri, "col_id": 1, "text": b, "bbox": [490, y0, 560, y1]},
            ]
        )
    return {"table_idx": 1, "cells": cells}


def test_devis_six_column_extracts_three_lines_with_tax_hints():
    subtotal = 24687.0 + 500.0 + 200.0
    assert subtotal == pytest.approx(25387.0)
    meta = {"provider": "surya", "surya_tables": [_devis_six_col_table()]}
    hints = {
        "subtotal_amount": subtotal,
        "tax_amount": subtotal * 0.19,
        "total_amount": subtotal * 1.19,
        "tax_rate_percent": 19.0,
    }
    lines, dbg = extract_invoice_lines_from_surya_metadata(meta, document_hints=hints)
    assert dbg.get("applied_to_draft") is True
    assert len(lines) == 3
    assert lines[0].description and "Transfo" in lines[0].description
    assert lines[0].quantity == pytest.approx(3.0)
    assert lines[0].unit_price == pytest.approx(8229.0)
    assert lines[0].line_subtotal == pytest.approx(24687.0)
    assert lines[0].details and "29377" in lines[0].details.replace(" ", "")
    gval = (dbg.get("table_correction") or {}).get("global_validation") or {}
    assert gval.get("line_tax_ok") is True
    assert gval.get("subtotal_ok") is True


def test_table_picker_prefers_main_grid_over_mini_totals_block():
    meta = {
        "provider": "surya",
        "surya_tables": [_mini_totals_two_col_table(), _devis_six_col_table()],
    }
    lines, dbg = extract_invoice_lines_from_surya_metadata(meta)
    assert dbg.get("best_table_idx") == 1
    assert len(lines) == 3


def test_devis_multi_rows_occluded_ttc_parsed_correctly():
    """Plusieurs lignes avec P.T.T.C sans point (photo réelle) : pas de millions fantômes."""
    yh, h, dy = 10, 22, 28

    def cell(r: int, col: int, txt: str, *, header: bool = False) -> dict:
        xcols = [(0, 10, 118), (1, 120, 158), (2, 160, 198), (3, 200, 268), (4, 270, 348), (5, 350, 438)]
        x0, x1 = xcols[col][1], xcols[col][2]
        if r == 0:
            y0, y1 = yh, yh + h
        else:
            y0 = yh + h + (r - 1) * dy
            y1 = y0 + h
        d = {"row_id": r, "col_id": col, "text": txt, "bbox": [x0, y0, x1, y1]}
        if header:
            d["is_header"] = True
        return d

    cells: list[dict] = []
    hdr = ["Désignation", "UNITE", "QTE", "P.U", "P.H.T", "P.T.T.C"]
    for col, tx in enumerate(hdr):
        cells.append(cell(0, col, tx, header=True))
    rows = [
        ("Équipement BT", "UN", "1", "5 810.000", "5 810.000", "6 913 900"),
        ("Plaque danger", "UN", "1", "70.000", "70.000", "83 300"),
        ("Fus 3H", "UN", "3", "30.000", "900.000", "1 071 000"),
    ]
    for ri, tx in enumerate(rows, start=1):
        for col in range(6):
            cells.append(cell(ri, col, tx[col]))
    t = {"table_idx": 0, "cells": cells}
    info = detect_table_columns(t)
    rows_out, _ = parse_surya_table_rows(t, column_info=info)
    assert len(rows_out) == 3
    assert rows_out[0].line_ttc == pytest.approx(6913.9)
    assert rows_out[1].line_ttc == pytest.approx(83.3)
    assert rows_out[2].line_ttc == pytest.approx(1071.0)


def test_parse_row_with_occluded_decimal_millimes_ttc():
    """Cellules P.T.T.C sans point (ex. photo devis) : 6 913 900 → 6913.900."""
    cells = [
        {"row_id": 0, "col_id": 0, "text": "Désignation", "is_header": True, "bbox": [0, 0, 80, 20]},
        {"row_id": 0, "col_id": 1, "text": "UN", "is_header": True, "bbox": [90, 0, 120, 20]},
        {"row_id": 0, "col_id": 2, "text": "QTE", "is_header": True, "bbox": [130, 0, 160, 20]},
        {"row_id": 0, "col_id": 3, "text": "P.U", "is_header": True, "bbox": [170, 0, 230, 20]},
        {"row_id": 0, "col_id": 4, "text": "P.H.T", "is_header": True, "bbox": [240, 0, 300, 20]},
        {"row_id": 0, "col_id": 5, "text": "P.T.T.C", "is_header": True, "bbox": [310, 0, 380, 20]},
        {"row_id": 1, "col_id": 0, "text": "Équipement BT", "bbox": [0, 25, 80, 45]},
        {"row_id": 1, "col_id": 1, "text": "UN", "bbox": [90, 25, 120, 45]},
        {"row_id": 1, "col_id": 2, "text": "1", "bbox": [130, 25, 160, 45]},
        {"row_id": 1, "col_id": 3, "text": "5 810.000", "bbox": [170, 25, 230, 45]},
        {"row_id": 1, "col_id": 4, "text": "5 810.000", "bbox": [240, 25, 300, 45]},
        {"row_id": 1, "col_id": 5, "text": "6 913 900", "bbox": [310, 25, 380, 45]},
    ]
    t = {"table_idx": 0, "cells": cells}
    info = detect_table_columns(t)
    rows, _ = parse_surya_table_rows(t, column_info=info)
    assert len(rows) == 1
    assert rows[0].line_ttc == pytest.approx(6913.9)


def test_parse_quantity_cell_single_digit_before_spurious_millimes():
    assert _parse_quantity_cell("4.760") == pytest.approx(4.0)
    assert _parse_quantity_cell("10") == pytest.approx(10.0)


def test_skip_devis_subtitle_row_construction_poste():
    cells = [
        {"row_id": 0, "col_id": 0, "text": "Désignation", "is_header": True, "bbox": [0, 0, 100, 20]},
        {"row_id": 0, "col_id": 1, "text": "QTE", "is_header": True, "bbox": [110, 0, 150, 20]},
        {"row_id": 0, "col_id": 2, "text": "P.U", "is_header": True, "bbox": [160, 0, 220, 20]},
        {"row_id": 0, "col_id": 3, "text": "P.H.T", "is_header": True, "bbox": [230, 0, 290, 20]},
        {"row_id": 1, "col_id": 0, "text": "Construction Poste 3 x 50 KVA", "bbox": [0, 25, 100, 45]},
        {"row_id": 1, "col_id": 1, "text": "0", "bbox": [110, 25, 150, 45]},
        {"row_id": 1, "col_id": 2, "text": "0", "bbox": [160, 25, 220, 45]},
        {"row_id": 1, "col_id": 3, "text": "0", "bbox": [230, 25, 290, 45]},
        {"row_id": 2, "col_id": 0, "text": "Fus 3H", "bbox": [0, 50, 100, 70]},
        {"row_id": 2, "col_id": 1, "text": "3", "bbox": [110, 50, 150, 70]},
        {"row_id": 2, "col_id": 2, "text": "30.000", "bbox": [160, 50, 220, 70]},
        {"row_id": 2, "col_id": 3, "text": "900.000", "bbox": [230, 50, 290, 70]},
    ]
    t = {"table_idx": 0, "cells": cells}
    info = detect_table_columns(t)
    rows, journal = parse_surya_table_rows(t, column_info=info)
    assert any("skip_subtitle_row" in j for j in journal)
    assert len(rows) == 1
    assert "Fus" in (rows[0].description or "")


def test_validate_rows_rescales_unit_price_power_of_ten():
    """OCR / lecture parfois gonfle le P.U d'un facteur 10^n alors que QTE × P.U = P.H.T."""
    rows = [
        TableRowModel(
            description="Transfo",
            quantity=3.0,
            unit_price=8_229_000.0,
            line_ht=24_687.0,
            line_ttc=None,
            source_row_id=1,
        )
    ]
    fixed, corr = validate_and_correct_rows(rows)
    assert any("pu_rescale_div_1000" in c for c in corr)
    assert fixed[0].unit_price == pytest.approx(8229.0)
    assert fixed[0].quantity == 3.0
