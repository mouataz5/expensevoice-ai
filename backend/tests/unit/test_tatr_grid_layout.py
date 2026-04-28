"""Grille Table Transformer (clustering sans inférence modèle)."""

from app.services.ocr.tatr_table_service import (
    _assign_grid_indices,
    _cluster_rows,
    _raw_text_from_cells,
    _Box,
)


def test_cluster_rows_builds_reading_order_grid() -> None:
    boxes = [
        _Box(10, 100, 50, 120, 5, 0.9),
        _Box(60, 100, 100, 120, 5, 0.88),
        _Box(10, 130, 50, 150, 5, 0.85),
        _Box(60, 130, 100, 150, 5, 0.87),
    ]
    rows = _cluster_rows(boxes, y_tol=25.0)
    assert len(rows) == 2
    assert len(rows[0]) == 2 and len(rows[1]) == 2
    cells = _assign_grid_indices(rows)
    assert cells[0]["row_id"] == 0 and cells[0]["col_id"] == 0
    assert cells[1]["col_id"] == 1
    assert cells[2]["row_id"] == 1


def test_raw_text_from_cells_orders_by_row_col() -> None:
    cells = [
        {"row_id": 0, "col_id": 0, "text": "A"},
        {"row_id": 0, "col_id": 1, "text": "B"},
        {"row_id": 1, "col_id": 0, "text": "C"},
    ]
    assert "A" in _raw_text_from_cells(cells)
    assert "B" in _raw_text_from_cells(cells)
    lines = _raw_text_from_cells(cells).split("\n")
    assert len(lines) == 2
