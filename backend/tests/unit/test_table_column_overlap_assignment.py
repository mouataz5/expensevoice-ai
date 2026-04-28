"""Assignation colonnes par chevauchement X (réduit les décalages vs. binning par xc seul)."""
from app.services.invoice_facades.table_geometry_core import (
    TableWordBox,
    assign_cells_to_column_intervals,
    column_intervals_from_header_cells,
)

HEADER = [
    [TableWordBox("Désignation", 0.0, 0.0, 100.0, 10.0)],
    [TableWordBox("Qte", 110.0, 0.0, 140.0, 10.0)],
    [TableWordBox("PU", 150.0, 0.0, 190.0, 10.0)],
    [TableWordBox("PHT", 200.0, 0.0, 260.0, 10.0)],
]


def test_assign_prefers_column_by_horizontal_overlap_not_only_center() -> None:
    """Mot large chevauchant la coupure : le centre peut tomer en colonne voisine."""
    iv = column_intervals_from_header_cells(HEADER)
    assert len(iv) == 4
    # Centre ~175 → entre PU et PHT ; chevauchement fort avec PU
    wide = TableWordBox("8229", 130.0, 20.0, 185.0, 30.0)
    cols = assign_cells_to_column_intervals([wide], iv)
    texts = [" ".join(w.text for w in col) for col in cols]
    assert texts[2] == "8229"


def test_multi_word_row_sorted_into_columns() -> None:
    iv = column_intervals_from_header_cells(HEADER)
    words = [
        TableWordBox("Poulet", 5.0, 20.0, 70.0, 30.0),
        TableWordBox("3", 115.0, 20.0, 125.0, 30.0),
        TableWordBox("1500", 158.0, 20.0, 182.0, 30.0),
        TableWordBox("4500", 205.0, 20.0, 245.0, 30.0),
    ]
    cols = assign_cells_to_column_intervals(words, iv)
    assert "Poulet" in cols[0][0].text
    assert cols[1][0].text == "3"
    assert "1500" in cols[2][0].text
    assert "4500" in cols[3][0].text
