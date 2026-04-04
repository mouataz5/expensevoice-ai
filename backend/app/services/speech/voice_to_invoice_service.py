"""
Transcription vocale (Whisper) → structure d'achat / vente via Groq (JSON strict).

Ciblée Tunisie : arabe dialectal tunisien, français, chiffres parlés (كليو، دينار، ألف…).
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from typing import Any

import httpx

from app.schemas.invoice_pipeline import InvoiceExtractionDraft, InvoiceExtractionResponse, InvoiceLineDraft
from app.services.confidence_scoring import compute_global_confidence
from app.services.invoice_validation_service import enrich_validation_confidence, validate_invoice_draft

logger = logging.getLogger(__name__)

VOICE_PURCHASE_SYSTEM_PROMPT = """\
Tu es un extracteur de lignes d'achat ou de vente à partir d'une phrase PARLÉE (souvent bruitée, dialecte tunisien arabe, français, mélange).

Tu reçois le texte brut (sortie Whisper). Tu dois produire UN SEUL objet JSON valide, sans markdown ni ```.

Règles strictes:
- Ne JAMAIS inventer d'article, quantité ou prix absents du texte. Si une information manque, mets quantity ou unit_price à null et ajoute une courte phrase dans "warnings".
- type: "achat" si achat / شراء / شريت / اشتريت / j'ai acheté ; "vente" si vente / بيع / بعت / j'ai vendu. Si ambigu, déduis du contexte ou mets "achat" + warning.
- Quantités: entiers ou décimaux (ex. 50 كيلو → 50). "نص" / "نصف" → 0.5 si clairement une quantité.
- Prix: nombres en dinars tunisiens (TND). Expressions tunisiennes: "ألف" ou "الف" souvent = 1000 (ex. "ثمانية ألف" → 8000). "مية" / "مائة" = 100. "عشرة" = 10.
- line_total doit valoir quantity * unit_price lorsque les deux sont connus (avec tolérance arrondi); sinon null.
- total = somme des line_total si toutes les lignes ont line_total; sinon meilleure estimation à partir du texte sans inventer.
- currency: presque toujours "TND" pour ce contexte.
- items: tableau d'objets { "name", "quantity", "unit_price", "line_total" } — name en arabe ou français comme dans le texte, court.

Schéma JSON exact (toutes les clés requises):
{
  "type": "achat",
  "items": [
    {"name": "", "quantity": null, "unit_price": null, "line_total": null}
  ],
  "total": null,
  "currency": "TND",
  "warnings": []
}

Si aucun article identifiable: items = [], total = null, warnings = ["aucun article détecté"].
Pas de texte hors JSON.
"""


def _safe_float(x: Any) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        if math.isnan(float(x)) or math.isinf(float(x)):
            return None
        return float(x)
    s = str(x).strip().replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _round_money(x: float) -> float:
    return round(x, 3)


def normalize_voice_purchase_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Valide la forme, recalcule line_total / total quand possible."""
    out: dict[str, Any] = {
        "type": "achat",
        "items": [],
        "total": None,
        "currency": "TND",
        "warnings": list(raw.get("warnings") or []) if isinstance(raw.get("warnings"), list) else [],
    }
    t = str(raw.get("type") or "achat").strip().lower()
    if t in ("vente", "sell", "sale"):
        out["type"] = "vente"
    elif t in ("achat", "buy", "purchase"):
        out["type"] = "achat"
    else:
        out["type"] = "achat"
        out["warnings"].append(f"type_ambigu:{t}")

    items_in = raw.get("items")
    if not isinstance(items_in, list):
        items_in = []

    norm_items: list[dict[str, Any]] = []
    for it in items_in:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip() or "—"
        q = _safe_float(it.get("quantity"))
        pu = _safe_float(it.get("unit_price"))
        lt = _safe_float(it.get("line_total"))
        if q is not None and pu is not None:
            expected = _round_money(q * pu)
            if lt is None:
                lt = expected
            elif abs(lt - expected) > max(0.05, abs(expected) * 0.02):
                out["warnings"].append(
                    f"ligne '{name}': line_total ajusté ({lt} → {expected})"
                )
                lt = expected
        norm_items.append(
            {
                "name": name,
                "quantity": q,
                "unit_price": pu,
                "line_total": _round_money(lt) if lt is not None else None,
            }
        )

    out["items"] = norm_items

    total = _safe_float(raw.get("total"))
    sum_lines = sum(
        (i["line_total"] or 0) for i in norm_items if i.get("line_total") is not None
    )
    if norm_items and all(i.get("line_total") is not None for i in norm_items):
        sum_lines = _round_money(sum_lines)
        if total is None:
            total = sum_lines
        elif abs(total - sum_lines) > max(1.0, abs(sum_lines) * 0.02):
            out["warnings"].append(f"total ajusté pour cohérence lignes ({total} → {sum_lines})")
            total = sum_lines
    out["total"] = _round_money(total) if total is not None else None

    cur = str(raw.get("currency") or "TND").strip().upper() or "TND"
    out["currency"] = cur

    return out


def _parse_groq_json(content: str) -> dict[str, Any]:
    s = (content or "").strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", s)
        if not m:
            raise
        obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("Groq voice purchase: not an object")
    return obj


async def _groq_voice_purchase(user_block: str) -> str:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY missing")
    model = os.getenv("GROQ_VOICE_MODEL") or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": VOICE_PURCHASE_SYSTEM_PROMPT},
            {"role": "user", "content": user_block},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
    data = r.json()
    return str(data.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()


def voice_purchase_to_extraction_response(
    *,
    raw_text: str,
    voice_purchase: dict[str, Any],
    transaction_type: str,
) -> InvoiceExtractionResponse:
    """Enveloppe pipeline (draft + validation + scores) pour ne pas casser les clients existants."""
    from app.services.invoice_global_pipeline import _synthetic_ocr_for_voice

    tt = (transaction_type or "buy").strip().lower()
    lines: list[InvoiceLineDraft] = []
    for it in voice_purchase.get("items") or []:
        if not isinstance(it, dict):
            continue
        lines.append(
            InvoiceLineDraft(
                description=str(it.get("name") or "") or None,
                quantity=it.get("quantity"),
                unit_price=it.get("unit_price"),
                line_subtotal=it.get("line_total"),
            )
        )

    warns = list(voice_purchase.get("warnings") or [])
    if not lines:
        warns = list({*warns, "Aucune ligne extraite du texte vocal"})

    draft = InvoiceExtractionDraft(
        document_type="invoice",
        supplier_name=None,
        invoice_number=None,
        invoice_date=None,
        currency=voice_purchase.get("currency") or "TND",
        items=lines,
        total_amount=voice_purchase.get("total"),
        subtotal_amount=voice_purchase.get("total"),
        warnings=warns,
        global_confidence=0.72 if lines else 0.25,
        missing_fields=["supplier_name", "invoice_number", "invoice_date"] if lines else [],
    )

    ocr = _synthetic_ocr_for_voice(raw_text)
    validation = validate_invoice_draft(draft, raw_text)
    validation = enrich_validation_confidence(validation)
    fc, gc = compute_global_confidence(ocr, draft, validation)
    draft.field_confidence = fc
    draft.global_confidence = gc
    validation.field_confidence = fc
    validation.global_confidence = gc

    success = bool(lines) and voice_purchase.get("total") is not None

    return InvoiceExtractionResponse(
        success=success,
        ocr_text=raw_text,
        normalized_text=raw_text,
        cleaned_text=raw_text,
        data=draft,
        validation=validation,
        warnings=list({*(draft.warnings or []), *(voice_purchase.get("warnings") or [])}),
        debug=None,
        ocr_metadata=dict(ocr.metadata or {}),
        post_corrections={},
    )


async def parse_voice_to_invoice(text: str, *, transaction_type: str = "buy") -> dict[str, Any]:
    """
    Texte (Whisper ou saisi) → JSON structuré achat/vente.

    transaction_type: "buy" | "sell" — indice pour le LLM (TRANSACTION_HINT).
    Retourne un dict avec type, items, total, currency, warnings (normalisé).
    """
    raw = (text or "").strip()
    if not raw:
        return normalize_voice_purchase_dict(
            {
                "type": "achat",
                "items": [],
                "total": None,
                "currency": "TND",
                "warnings": ["texte vide"],
            }
        )

    tt = (transaction_type or "buy").strip().lower()
    if tt not in ("sell", "buy"):
        tt = "buy"
    hint = "achat (buy)" if tt == "buy" else "vente (sell)"
    user_block = f"TRANSACTION_HINT: {hint}\n\nSPOKEN_TEXT:\n{raw}\n"

    try:
        raw_out = await _groq_voice_purchase(user_block)
        obj = _parse_groq_json(raw_out)
    except Exception as e:
        logger.warning("parse_voice_to_invoice Groq failed: %s", str(e)[:300])
        return normalize_voice_purchase_dict(
            {
                "type": "achat" if tt == "buy" else "vente",
                "items": [],
                "total": None,
                "currency": "TND",
                "warnings": [f"groq_error:{str(e)[:120]}"],
            }
        )

    normalized = normalize_voice_purchase_dict(obj)
    if tt == "sell" and normalized.get("type") == "achat":
        normalized.setdefault("warnings", []).append("transaction_type_hint_was_sell")
    return normalized
