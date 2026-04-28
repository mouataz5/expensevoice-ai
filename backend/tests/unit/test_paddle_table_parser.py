"""Conversion HTML table Paddle → grille `cells`."""
from __future__ import annotations

from app.services.ocr.paddle_html_table_parser import cells_from_paddle_pred_html


def test_cells_from_pred_html_matches_header_and_boxes():
    html = (
        "<html><body><table>"
        "<tr><th>Désignation</th><th>QTE</th></tr>"
        "<tr><td>Item A</td><td>5</td></tr>"
        "</table></body></html>"
    )
    boxes = [
        [0.0, 0.0, 10.0, 10.0],
        [10.0, 0.0, 20.0, 10.0],
        [0.0, 10.0, 10.0, 20.0],
        [10.0, 10.0, 20.0, 20.0],
    ]
    cells = cells_from_paddle_pred_html(html, boxes)
    assert len(cells) == 4
    assert cells[0]["row_id"] == 0 and cells[0]["col_id"] == 0
    assert cells[0]["is_header"] is True
    assert cells[0]["text"] == "Désignation"
    assert cells[2]["text"] == "Item A"
    assert cells[2]["bbox"] == [0.0, 10.0, 10.0, 20.0]


def test_parse_tunisian_amount_alias():
    from app.utils.amount_normalization import parse_tunisian_amount

    assert parse_tunisian_amount("8 229.000") == 8229.0
    assert parse_tunisian_amount("83 300") == 83300.0
