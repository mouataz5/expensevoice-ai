"""
Heuristiques et réconciliation facture — façade stable au-dessus du module legacy.

Le code métier reste dans `invoice_extraction` (regex, montants, etc.) ;
les nouveaux modules du pipeline global importent depuis ce fichier pour
limiter le couplage et clarifier les responsabilités.
"""
from __future__ import annotations

from app.services.invoice_extraction import (
    heuristic_invoice_from_ocr,
    reconcile_extracted_invoice_numbers,
)

__all__ = [
    "heuristic_invoice_from_ocr",
    "reconcile_extracted_invoice_numbers",
]
