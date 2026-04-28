"""
Mode strict extraction tabulaire (production) : tableau structuré ou échec explicite.

Activé avec INVOICE_STRICT_TABLE_EXTRACTION=1. Désactivé par défaut pour les tests / OCR texte seul.
"""
from __future__ import annotations

import os
from typing import Any

from app.services.invoice_facades.table_numeric_repair import _MAX_QTY

TABLE_EXTRACTION_FAILED = "TABLE_EXTRACTION_FAILED"
INVALID_TABLE_MATH = "INVALID_TABLE_MATH"

STRICT_FAILURE_MESSAGES_FR: dict[str, str] = {
    TABLE_EXTRACTION_FAILED: "Impossible d'extraire le tableau de manière fiable",
    INVALID_TABLE_MATH: "Les montants des lignes extraites ne sont pas cohérents (qté × prix unitaire).",
}


def strict_failure_message_fr(code: str) -> str:
    return STRICT_FAILURE_MESSAGES_FR.get(
        code,
        STRICT_FAILURE_MESSAGES_FR[TABLE_EXTRACTION_FAILED],
    )

_STRICT_ENV = "INVOICE_STRICT_TABLE_EXTRACTION"

# Providers pour lesquels on exige une grille si le mode strict est actif (pas transcription vocale).
_SKIP_STRICT_PROVIDERS = frozenset({"voice_transcript", "manual"})


def strict_table_extraction_enabled() -> bool:
    return (os.getenv(_STRICT_ENV) or "").strip().lower() in ("1", "true", "yes", "on")


def strict_table_applies_for_ocr(metadata: dict[str, Any] | None) -> bool:
    if not strict_table_extraction_enabled():
        return False
    prov = str((metadata or {}).get("provider") or "").strip().lower()
    if prov in _SKIP_STRICT_PROVIDERS:
        return False
    return True


def ocr_metadata_has_structured_table_payload(metadata: dict[str, Any] | None) -> bool:
    """Présence de grilles candidates (PP-Structure ou Surya)."""
    meta = metadata or {}
    st = meta.get("structured_tables")
    if isinstance(st, list) and any(isinstance(t, dict) and (t.get("cells") or t.get("n_cells")) for t in st):
        return True
    if str(meta.get("provider") or "").lower() == "surya":
        surya = meta.get("surya_tables")
        if isinstance(surya, list) and len(surya) > 0:
            return True
    return False


def structured_lines_math_valid(
    lines: list[Any],
    *,
    tol_ratio: float = 0.04,
    tol_abs: float = 3.0,
) -> bool:
    """
    Chaque ligne avec qté, PU et HT > 0 doit vérifier qté×PU ≈ HT et
    les quantités doivent rester plausibles (borne supérieure globale).

    Cette fonction est utilisée comme garde-fou **avant** d'appliquer des
    lignes issues d'un tableau structuré au brouillon facture. En cas de
    doute sur une seule ligne, on invalide tout le tableau pour éviter un
    « faux positif » de confiance.
    """
    if not lines:
        return False
    from app.utils.money import to_float_safe

    for ln in lines:
        q = to_float_safe(getattr(ln, "quantity", None))
        pu = to_float_safe(getattr(ln, "unit_price", None))
        st = to_float_safe(getattr(ln, "line_subtotal", None))
        if st is None or st <= 0:
            return False
        if q is None or q <= 0 or pu is None or pu <= 0:
            return False
        # borne supérieure globale pour éviter les aberrations (ex: 679490)
        if float(q) > float(_MAX_QTY):
            return False
        exp = float(q) * float(pu)
        t = max(tol_abs, abs(float(st)) * tol_ratio)
        if abs(exp - float(st)) > t:
            return False
    return True


__all__ = [
    "TABLE_EXTRACTION_FAILED",
    "INVALID_TABLE_MATH",
    "STRICT_FAILURE_MESSAGES_FR",
    "strict_failure_message_fr",
    "strict_table_extraction_enabled",
    "strict_table_applies_for_ocr",
    "ocr_metadata_has_structured_table_payload",
    "structured_lines_math_valid",
]
