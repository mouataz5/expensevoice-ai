"""
Conversion des sorties tabulaires Paddle (PP-Structure / TableRecognition) vers la grille
`cells` (row_id, col_id, text, bbox, is_header) consommée par `surya_table_extractor`.
"""
from __future__ import annotations

import re
from html import unescape
from typing import Any


_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_CELL_RE = re.compile(
    r"<(th|td)([^>]*)>(.*?)</\1>",
    re.IGNORECASE | re.DOTALL,
)


def _strip_html_cell_fragment(raw: str) -> str:
    t = raw or ""
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return unescape(t).replace("\r", "").strip()


def cells_from_paddle_pred_html(
    pred_html: str | None,
    cell_box_list: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Interprète le HTML produit par PaddleX (lignes / cellules dans l'ordre lecture)
    et aligne les bbox `cell_box_list` (même ordre que les <td>/<th>).
    """
    html = (pred_html or "").strip()
    if not html:
        return []
    boxes = cell_box_list or []
    cells: list[dict[str, Any]] = []
    flat_idx = 0
    row_id = 0
    for tr_m in _TR_RE.finditer(html):
        inner = tr_m.group(1) or ""
        col_id = 0
        for c_m in _CELL_RE.finditer(inner):
            tag = (c_m.group(1) or "td").lower()
            frag = c_m.group(3) or ""
            text = _strip_html_cell_fragment(frag)
            bbox: list[float] | None = None
            if flat_idx < len(boxes):
                b = boxes[flat_idx]
                try:
                    bbox = [float(b[0]), float(b[1]), float(b[2]), float(b[3])]
                except (TypeError, ValueError, IndexError):
                    bbox = None
            cells.append(
                {
                    "row_id": row_id,
                    "col_id": col_id,
                    "text": text,
                    "bbox": bbox,
                    "is_header": tag == "th",
                }
            )
            col_id += 1
            flat_idx += 1
        row_id += 1
    return cells


def surya_compatible_table_from_paddle_result(
    *,
    page_index: int | None,
    table_index: int,
    pred_html: str | None,
    cell_box_list: list[Any] | None,
) -> dict[str, Any]:
    """Enveloppe une table Paddle au même format minimal que `surya_tables[]`."""
    cells = cells_from_paddle_pred_html(pred_html, cell_box_list)
    return {
        "page": page_index,
        "table_idx": table_index,
        "cells": cells,
        "n_cells": len(cells),
        "source": "paddle_pp_structure",
    }


__all__ = [
    "cells_from_paddle_pred_html",
    "surya_compatible_table_from_paddle_result",
]
