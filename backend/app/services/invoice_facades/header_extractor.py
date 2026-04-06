"""
Extraction en-tête / fournisseur (bloc société, numéro, date, MF).

Délègue aux heuristiques existantes pour ne pas dupliquer les regex métier.
"""
from __future__ import annotations

from typing import Any

from app.services.invoice_heuristics import extract_invoice_header, extract_supplier_block

__all__ = ["extract_supplier_block", "extract_invoice_header"]


def extract_header_fields(ocr_text: str, *, transaction_type: str = "buy") -> dict[str, Any]:
    """Vue agrégée : en-tête structuré + bloc fournisseur brut."""
    return {
        "header": extract_invoice_header(ocr_text or ""),
        "supplier_block": extract_supplier_block(ocr_text or "", transaction_type),
    }
