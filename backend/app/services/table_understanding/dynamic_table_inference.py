"""
Inférence dynamique des colonnes : en-têtes, géométrie (X), cohérence des types sur un échantillon.

S'appuie sur la détection existante `detect_table_columns` (Surya) et expose une API stable
pour d'autres backends (PP-Structure) derrière le même contrat.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.invoice_facades.surya_table_extractor import detect_table_columns
from app.utils.amount_normalization import parse_tunisian_amount


def detect_header_row_cells(cells: list[dict[str, Any]]) -> set[int]:
    """Indices de lignes considérées comme en-tête (flag ou contenu typique)."""
    header_ids: set[int] = set()
    for c in cells:
        if c.get("is_header"):
            try:
                header_ids.add(int(c["row_id"]))
            except (TypeError, ValueError):
                pass
    if header_ids:
        return header_ids
    by_row: dict[int, list[str]] = {}
    for c in cells:
        try:
            rid = int(c.get("row_id", -1))
        except (TypeError, ValueError):
            continue
        by_row.setdefault(rid, []).append(str(c.get("text") or ""))
    if not by_row:
        return set()
    min_row = min(by_row.keys())
    blob = " ".join(by_row[min_row]).lower()
    if re.search(r"qte|qté|quant|désign|p\.?\s*u|montant|ht|ttc|unit", blob, re.I):
        return {min_row}
    return set()


def infer_column_roles(table: dict[str, Any], *, cells: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """
    Produit { col_roles, header_row_ids, col_x_order } pour une table brute Surya-like.

    `table` doit contenir au minimum 'cells' (liste de dict normalisés).
    """
    return detect_table_columns(table, cells=cells)


def row_numeric_consistency_score(
    cells: list[dict[str, Any]],
    col_id: int,
    data_row_ids: list[int],
) -> float:
    """Part de lignes où la colonne `col_id` est parseable comme montant TN."""
    if not data_row_ids:
        return 0.0
    parseable = 0
    for rid in data_row_ids:
        texts = [
            str(c.get("text") or "").strip()
            for c in cells
            if int(c.get("row_id", -999)) == rid and int(c.get("col_id", -999)) == col_id
        ]
        joined = " ".join(texts).strip()
        if joined and parse_tunisian_amount(joined) is not None:
            parseable += 1
    return parseable / max(1, len(data_row_ids))


def map_cells_to_semantic_columns(
    table: dict[str, Any],
    column_info: dict[str, Any],
) -> dict[str, Any]:
    """Attache les rôles colonnes à la table (pass-through + métadonnées)."""
    return {
        **column_info,
        "table_idx": table.get("table_idx"),
        "page": table.get("page"),
    }


__all__ = [
    "detect_header_row_cells",
    "infer_column_roles",
    "map_cells_to_semantic_columns",
    "row_numeric_consistency_score",
]
