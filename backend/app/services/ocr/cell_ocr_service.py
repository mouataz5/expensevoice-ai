"""
Normalisation des cellules OCR : texte, bbox, indices grille, confiance agrégée.
"""
from __future__ import annotations

from typing import Any


def normalize_cell(raw: dict[str, Any] | Any, *, default_confidence: float | None = None) -> dict[str, Any]:
    """Uniformise une cellule vers le schéma pipeline dynamique."""
    if isinstance(raw, dict):
        text = str(raw.get("text") or "").strip()
        bb = raw.get("bbox")
        rid = raw.get("row_id")
        cid = raw.get("col_id")
        is_hdr = bool(raw.get("is_header"))
        conf = raw.get("confidence")
    else:
        text = str(getattr(raw, "text", "") or "").strip()
        bb = getattr(raw, "bbox", None)
        rid = getattr(raw, "row_id", None)
        cid = getattr(raw, "col_id", None)
        is_hdr = bool(getattr(raw, "is_header", False))
        conf = getattr(raw, "confidence", None)

    bbox_list: list[float] | None = None
    if bb is not None and len(bb) >= 4:
        try:
            bbox_list = [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]
        except (TypeError, ValueError):
            bbox_list = None

    try:
        row_id = int(rid) if rid is not None else -1
    except (TypeError, ValueError):
        row_id = -1
    try:
        col_id = int(cid) if cid is not None else -1
    except (TypeError, ValueError):
        col_id = -1

    try:
        c_f = float(conf) if conf is not None else default_confidence
    except (TypeError, ValueError):
        c_f = default_confidence

    return {
        "text": text,
        "bbox": bbox_list,
        "row_id": row_id,
        "col_id": col_id,
        "is_header": is_hdr,
        "confidence": c_f,
    }


def cells_from_table_dict(table: dict[str, Any]) -> list[dict[str, Any]]:
    """Convertit la liste brute `table['cells']` en cellules normalisées."""
    cells = table.get("cells") or []
    return [normalize_cell(c) for c in cells if c is not None]


__all__ = ["normalize_cell", "cells_from_table_dict"]
