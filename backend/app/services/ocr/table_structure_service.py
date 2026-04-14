"""
Détection de structure tabulaire : régions, lignes, colonnes, cellules.

Source principale aujourd'hui : métadonnées `surya_tables` (TableRec Surya).
Point d'extension futur : PP-Structure / Table Transformer — même contrat de sortie.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TableStructure:
    """Une grille détectée (une page / un indice de table)."""

    table_idx: int | None
    page: int | None
    cells: list[dict[str, Any]]
    n_cells_raw: int = 0
    source: str = "surya_table_rec"
    extra: dict[str, Any] = field(default_factory=dict)


def extract_table_structures_from_ocr_metadata(metadata: dict[str, Any] | None) -> list[TableStructure]:
    """
    Lit `metadata['surya_tables']` et produit des structures normalisées.

    Chaque élément attendu : { table_idx, page, cells: [{text, bbox, row_id, col_id, is_header}] }.
    """
    if not metadata:
        return []
    raw_tables = metadata.get("surya_tables") or []
    out: list[TableStructure] = []
    for i, tbl in enumerate(raw_tables):
        if not isinstance(tbl, dict):
            continue
        cells_in = tbl.get("cells") or []
        if not cells_in:
            continue
        out.append(
            TableStructure(
                table_idx=tbl.get("table_idx") if tbl.get("table_idx") is not None else i,
                page=tbl.get("page"),
                cells=list(cells_in)[:800],
                n_cells_raw=int(tbl.get("n_cells") or len(cells_in)),
                source="surya_table_rec",
                extra={"raw_keys": list(tbl.keys())},
            )
        )
    return out


def pick_largest_table(structures: list[TableStructure]) -> TableStructure | None:
    """Heuristique : table avec le plus de cellules (hors en-tête seul)."""
    if not structures:
        return None
    return max(structures, key=lambda s: len(s.cells))


__all__ = [
    "TableStructure",
    "extract_table_structures_from_ocr_metadata",
    "pick_largest_table",
]
