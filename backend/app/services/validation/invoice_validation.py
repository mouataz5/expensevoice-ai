"""
Validation métier factures — façade sur `invoice_validation_service`.

Garde une entrée unique pour les contrôles arithmétiques / de cohérence.
"""
from __future__ import annotations

from app.services.invoice_validation_service import (
    enrich_validation_confidence,
    validate_invoice_draft,
)

__all__ = ["validate_invoice_draft", "enrich_validation_confidence"]
