"""
Extraction des totaux (HTVA, TVA, timbre, TTC, paiements) depuis le texte OCR.

Façade sur `invoice_heuristics.detect_totals` et `invoice_table_parser.extract_totals_from_text`.
"""
from __future__ import annotations

from typing import Any

from app.services.invoice_heuristics import detect_totals
from app.services.invoice_table_parser import extract_totals_from_text

__all__ = ["detect_totals", "extract_totals_from_text", "extract_all_totals"]


def extract_all_totals(ocr_text: str) -> dict[str, Any]:
    """Combine les deux vues : tuple heuristique + dict étendu libellés."""
    compact = detect_totals(ocr_text or "")
    extended = extract_totals_from_text(ocr_text or "")
    return {"compact": compact, "extended": extended}
