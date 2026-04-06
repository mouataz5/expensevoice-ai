"""
Extraction bloc client (nom, adresse, MF client).

Façade sur `invoice_heuristics` / `invoice_extraction`.
"""
from __future__ import annotations

from typing import Any

from app.services.invoice_heuristics import extract_client_block

__all__ = ["extract_client_block"]


def extract_client_fields(ocr_text: str) -> dict[str, Any]:
    """Retour du bloc client tel que parsé par les heuristiques actuelles."""
    return extract_client_block(ocr_text or "")
