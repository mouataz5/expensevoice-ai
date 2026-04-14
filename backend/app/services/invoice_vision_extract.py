"""
Extraction directe depuis l'image via un modèle Vision (Groq Llama 4 Scout).

Envoie l'image en base64 au modèle multimodal qui *voit* le tableau ;
retourne un InvoiceExtractionDraft structuré — pas de parsing OCR de colonnes.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx

from app.schemas.invoice_pipeline import InvoiceExtractionDraft

logger = logging.getLogger(__name__)

_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

VISION_SYSTEM_PROMPT = """\
Tu es un expert en extraction de données depuis des documents financiers scannés (factures, devis, bons de livraison).
Tu reçois une IMAGE du document. Tu dois extraire TOUTES les informations structurées.

=== RÈGLES CRITIQUES ===
1. Lis directement ce que tu VOIS dans l'image — ne devine rien.
2. Le contexte est tunisien/français. Montants en TND (millimes = 3 décimales après le point).
3. Formats nombres TN : espaces = séparateurs de milliers, dernier groupe de 3 après point/virgule = millimes.
   Exemples : "8 229.000" = 8229.000 TND, "53 137.070" = 53137.070 TND, "83 300" = 83.300 TND
4. Extrais TOUTES les lignes du tableau articles avec designation, quantity, unit_price, line_subtotal.
5. quantity doit être un entier raisonnable (1, 2, 3, 4...) PAS un nombre à 6 chiffres.
6. unit_price est le prix par unité en TND (nombre raisonnable, PAS en millimes).
7. line_subtotal = quantity × unit_price (vérifie la cohérence).
8. Extrais les totaux : subtotal_amount (Total HT), tax_amount (TVA), total_amount (Total TTC).
9. invoice_number : N° facture, N° devis, réf., FAC-..., DV-..., etc.
10. Dates en YYYY-MM-DD.

=== SCHÉMA JSON (toutes clés, null si absent) ===
{
  "document_type": "invoice" ou "quote",
  "supplier_name": "...",
  "supplier_full_name": "...",
  "client_name": "...",
  "invoice_number": "...",
  "invoice_date": "YYYY-MM-DD",
  "payment_due_date": null,
  "client_tax_id": "...",
  "client_city": null,
  "client_address": null,
  "supplier_tax_id": "...",
  "supplier_phone": "...",
  "supplier_address": "...",
  "tax_rate_percent": 19,
  "currency": "TND",
  "items": [
    {"description": "...", "details": null, "quantity": 3, "unit_price": 8229.0, "line_subtotal": 24687.0}
  ],
  "subtotal_amount": 44723.0,
  "tax_amount": 8407.07,
  "stamp_tax": null,
  "total_amount": 53137.07,
  "amount_paid": null,
  "remaining_due": null,
  "warnings": [],
  "missing_fields": [],
  "field_confidence": {"supplier_name": 0.9, "invoice_number": 0.9, "invoice_date": 0.9, "total_amount": 0.9, "client_name": 0.85},
  "global_confidence": 0.85
}

Réponds UNIQUEMENT avec le JSON, sans markdown ni texte avant/après.
"""


def _encode_image(image_path: str) -> tuple[str, str]:
    """Base64 + mime type depuis le fichier."""
    p = Path(image_path)
    suffix = p.suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/jpeg")
    data = p.read_bytes()
    if len(data) > 4 * 1024 * 1024:
        try:
            from PIL import Image
            import io

            img = Image.open(str(p))
            if img.mode not in ("RGB",):
                img = img.convert("RGB")
            w, h = img.size
            max_dim = 1800
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            data = buf.getvalue()
            mime = "image/jpeg"
        except Exception:
            pass
    return base64.b64encode(data).decode("ascii"), mime


def _parse_vision_response(raw: str) -> InvoiceExtractionDraft:
    s = (raw or "").strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", s)
        if not m:
            raise ValueError("Vision model did not return JSON")
        obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("Vision output not a dict")
    for k in ("invoice", "result", "data", "extraction"):
        if k in obj and isinstance(obj[k], dict):
            inner = obj[k]
            if "items" in inner or "document_type" in inner:
                obj = inner
                break
    return InvoiceExtractionDraft.model_validate(obj)


async def extract_invoice_from_image_vision(
    image_path: str,
    transaction_type: str = "buy",
) -> tuple[InvoiceExtractionDraft, str]:
    """
    Envoie l'image au modèle Vision Groq et retourne (draft, raw_response).

    Nécessite GROQ_API_KEY. Retourne un draft fallback si échec.
    """
    key = os.getenv("GROQ_API_KEY")
    if not key:
        logger.warning("GROQ_API_KEY missing — vision extraction skipped")
        return InvoiceExtractionDraft(
            warnings=["vision_extraction_skipped:no_api_key"],
            global_confidence=0.0,
        ), ""

    if not Path(image_path).is_file():
        logger.warning("Vision: image not found %s", image_path)
        return InvoiceExtractionDraft(
            warnings=["vision_extraction_skipped:file_not_found"],
            global_confidence=0.0,
        ), ""

    b64, mime = _encode_image(image_path)
    model = os.getenv("GROQ_VISION_MODEL", _VISION_MODEL)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"TRANSACTION_TYPE: {transaction_type}\n\nExtrait toutes les données de ce document financier.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{b64}",
                        },
                    },
                ],
            },
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }

    raw_out = ""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            r.raise_for_status()
        data = r.json()
        raw_out = str(
            data.get("choices", [{}])[0].get("message", {}).get("content", "")
        ).strip()
        draft = _parse_vision_response(raw_out)
        draft.warnings = list({*(draft.warnings or []), "source:vision_llm"})
        logger.info("Vision extraction OK: %d items, total=%s", len(draft.items or []), draft.total_amount)
        return draft, raw_out
    except httpx.HTTPStatusError as e:
        logger.warning("Vision API HTTP error: %s %s", e.response.status_code, str(e)[:200])
        return InvoiceExtractionDraft(
            warnings=[f"vision_api_error:{e.response.status_code}"],
            global_confidence=0.0,
        ), raw_out
    except Exception as e:
        logger.warning("Vision extraction failed: %s", str(e)[:300])
        return InvoiceExtractionDraft(
            warnings=[f"vision_extraction_failed:{str(e)[:150]}"],
            global_confidence=0.0,
        ), raw_out


def is_vision_available() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))


__all__ = ["extract_invoice_from_image_vision", "is_vision_available"]
