"""
Client Groq pour extraction facture structurée (JSON).

Utilise le même schéma / prompt que invoice_llm_extract pour cohérence pipeline.
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.invoice_pipeline import InvoiceExtractionDraft
from app.services.invoice_llm_extract import (
    INVOICE_GLOBAL_SYSTEM_PROMPT,
    _fallback_draft,
    _groq,
    _parse_draft,
)

logger = logging.getLogger(__name__)


async def extract_invoice_structured_data(
    raw_text: str,
    transaction_type: str = "buy",
) -> tuple[InvoiceExtractionDraft, str]:
    """
    Envoie le texte OCR (nettoyé) à Groq et retourne le draft validé + réponse brute.
    """
    user = (
        f"TRANSACTION_TYPE: {transaction_type}\n\n"
        f"OCR_TEXT:\n{raw_text}\n"
    )
    raw_out = ""
    try:
        raw_out = await _groq(user)
        draft = _parse_draft(raw_out)
        return draft, raw_out
    except Exception as e:
        logger.warning("Groq extraction parse/call failed: %s", str(e)[:300])
        d = _fallback_draft()
        d.warnings = list({*(d.warnings or []), f"groq: {str(e)[:200]}"})
        return d, raw_out or str(e)


async def extract_invoice_structured_data_as_dict(
    raw_text: str,
    transaction_type: str = "buy",
) -> tuple[dict[str, Any], str]:
    """Même chose mais dict JSON-sérialisable (API / tests)."""
    draft, raw = await extract_invoice_structured_data(raw_text, transaction_type)
    return draft.model_dump(), raw


def system_prompt() -> str:
    """Expose le prompt système (debug / outils)."""
    return INVOICE_GLOBAL_SYSTEM_PROMPT
