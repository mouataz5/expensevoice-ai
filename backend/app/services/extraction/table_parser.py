"""
Parsing déterministe de tableaux articles — OCR texte + optionnellement cellules Surya.

Les fonctions historiques vivent dans `invoice_table_parser` ; ce module expose une API stable
et colle au pipeline (enrichissement `raw_ocr` quand Surya fournit des cellules).
"""
from __future__ import annotations

import logging
import os
from typing import Any

from app.services import invoice_table_parser as _parser

logger = logging.getLogger(__name__)

__all__ = [
    "detect_invoice_table_lines",
    "line_items_from_table_detection",
    "merge_parser_line_items",
    "enrich_raw_ocr_with_surya_tables",
]


def _env_bool(key: str, default: str) -> bool:
    return (os.getenv(key, default) or default).strip().lower() in ("1", "true", "yes", "on")


def detect_invoice_table_lines(ocr_text: str) -> list[dict[str, Any]]:
    return _parser.detect_invoice_table_lines(ocr_text or "")


def line_items_from_table_detection(ocr_text: str) -> list[dict[str, Any]]:
    return _parser.line_items_from_table_detection(ocr_text or "")


def merge_parser_line_items(
    ocr_raw: str,
    glued_text: str,
    existing: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _parser.merge_parser_line_items(ocr_raw, glued_text, existing)


def _flatten_surya_cell_texts(metadata: dict[str, Any]) -> str:
    lines_out: list[str] = []
    for tbl in metadata.get("surya_tables") or []:
        cells = tbl.get("cells") or []
        scored: list[tuple[int, int, str]] = []
        for c in cells:
            if not isinstance(c, dict):
                continue
            rid = c.get("row_id")
            cid = c.get("col_id")
            tx = (c.get("text") or "").strip()
            if not tx:
                continue
            try:
                ri = int(rid) if rid is not None else 0
            except (TypeError, ValueError):
                ri = 0
            try:
                ci = int(cid) if cid is not None else 0
            except (TypeError, ValueError):
                ci = 0
            scored.append((ri, ci, tx))
        scored.sort(key=lambda x: (x[0], x[1]))
        if scored:
            lines_out.append("\t".join(t for _, _, t in scored))
    return "\n".join(lines_out).strip()


def enrich_raw_ocr_with_surya_tables(raw_ocr: str, metadata: dict[str, Any] | None) -> str:
    """
    Ajoute le texte des cellules reconnues par Surya à la fin du brut OCR pour les heuristiques
    (articles / totaux), sans remplacer le flux principal.

    Fallback / debug uniquement : définir SURYA_APPEND_TABLE_CELLS=1 pour regrouper les cellules
    dans le brut OCR (évité en prod : extraction structurée via `surya_table_extractor`).
    """
    meta = metadata or {}
    block = _flatten_surya_cell_texts(meta)
    if not block:
        return raw_ocr or ""
    if meta.get("provider") != "surya":
        return raw_ocr or ""
    if not _env_bool("SURYA_APPEND_TABLE_CELLS", "0"):
        return raw_ocr or ""
    base = (raw_ocr or "").rstrip()
    if block in base:
        return base
    logger.debug("enriching OCR with Surya table cell texts (%d chars)", len(block))
    return f"{base}\n\n[SURYA_TABLE_CELLS]\n{block}" if base else block
