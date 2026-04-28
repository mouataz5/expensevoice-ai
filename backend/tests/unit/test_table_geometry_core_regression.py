"""Non-régression : assignation colonnes par seuils d'en-tête + réparation perm3."""
from __future__ import annotations

import pytest

from app.services.invoice_facades.geometry_table_extractor import (
    _assign_row_to_columns,
    _map_header_cell_roles,
    _row_model_from_cells,
)
from app.services.invoice_facades.surya_table_extractor import TableRowModel, validate_and_correct_rows
from app.services.invoice_facades.table_geometry_core import TableWordBox


def _six_col_header() -> list[list[TableWordBox]]:
    return [
        [TableWordBox("Désignation", 10, 0, 180, 12)],
        [TableWordBox("UN", 200, 0, 220, 12)],
        [TableWordBox("QTE", 225, 0, 245, 12)],
        [TableWordBox("P.U", 250, 0, 280, 12)],
        [TableWordBox("P.HT", 290, 0, 330, 12)],
        [TableWordBox("P.TTC", 340, 0, 400, 12)],
    ]


def test_assign_columns_transfo_row_matches_expected_amounts() -> None:
    """Même avec un mot désignation large, les coupures X issues de l'en-tête gardent PU/HT dans les bonnes colonnes."""
    header = _six_col_header()
    roles = _map_header_cell_roles(header)
    data_row = [
        TableWordBox("Transfo mono 50 kVA", 12, 20, 175, 32),
        TableWordBox("U", 202, 20, 218, 32),
        TableWordBox("3", 228, 20, 242, 32),
        TableWordBox("8 229.000", 252, 20, 318, 32),
        # Centre X dans la bande P.HT (avant la coupure avec P.TTC), pas dans la colonne TTC.
        TableWordBox("24 687.000", 300, 20, 328, 32),
    ]
    cells = _assign_row_to_columns(data_row, header)
    tm = _row_model_from_cells(cells, roles, 0)
    assert tm is not None
    assert tm.quantity == pytest.approx(3)
    assert tm.unit_price == pytest.approx(8229.0)
    assert tm.line_ht == pytest.approx(24687.0)


def test_repair_perm3_swapped_qty_and_pu() -> None:
    """Colonne QTE/PU inversées numériquement : réparation par permutations."""
    r = TableRowModel(
        description="Test line",
        unit="U",
        quantity=8229.0,
        unit_price=3.0,
        line_ht=24687.0,
        source_row_id=0,
    )
    fixed, notes = validate_and_correct_rows([r])
    assert any("numeric_columns_repaired_perm3" in n for n in notes)
    assert fixed[0].quantity == pytest.approx(3)
    assert fixed[0].unit_price == pytest.approx(8229.0)
    assert fixed[0].line_ht == pytest.approx(24687.0)
