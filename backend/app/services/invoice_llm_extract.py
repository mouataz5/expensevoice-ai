"""
Extraction structurée facture via LLM (schéma global).

Providers: LLM_PROVIDER = ollama | openai | groq | mcp | fallback
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

from app.schemas.invoice_pipeline import InvoiceExtractionDraft, InvoiceLineDraft

logger = logging.getLogger(__name__)

INVOICE_GLOBAL_SYSTEM_PROMPT = """\
Tu es un extracteur de factures pour documents scannés (OCR bruité).
Langues: français prioritaire; arabe/anglais possibles. Contexte Tunisie fréquent.

Tu reçois du texte OCR (peut contenir erreurs). Tu dois produire UN SEUL objet JSON valide, sans markdown ni ```.

Règles strictes:
- Ne JAMAIS inventer de montants, dates ou noms non présents dans le texte. Si doute -> null + warning court dans "warnings".
- Dates: invoice_date et payment_due_date en ISO YYYY-MM-DD uniquement si le jour/mois/année est CALENDRIER VALIDE (jour 1–31, mois 1–12). Ne jamais sortir un jour > 31 ou un mois > 12. Si l'OCR montre un jour impossible (ex. 36/01/2026), choisir la correction la plus probable proche dans le texte (souvent 16 pour 36) et l'indiquer dans "warnings".
- Priorité pour invoice_date: la valeur sur la même ligne ou immédiatement après "DATE DE LA FACTURE", "DATE FACTURE", "DATE DE FACTURE" — pas une autre date (échéance) si ambigu.
- supplier_name: en-tête / émetteur (haut de page, avant bloc client), pas la ligne sous SOCIETE.
- invoice_number: la valeur après "N° FACTURE", "N FACTURE", "FACTURE N°", "No FACTURE" (référence type FA005/2026).
- client_name: obligatoire si présent dans le texte — typiquement la ligne juste après un libellé "SOCIETE :" ou "SOCIETE" seul sur une ligne, ou après "CLIENT" / "DESTINATAIRE".
- Corrections OCR lexicales (ne pas inventer un produit absent): en contexte volaille/alimentaire, "chat" isolé comme nom de produit -> probablement "chair" (ex. poussin chair). Autres confusions: mots très courts proches du libellé table (ARTICLE, DESIGNATION).
- Montants dans le JSON: nombres décimaux avec point (ex: 15575.0 pour quinze mille cinq cent soixante-quinze dinars et zéro millime). Pas de chaînes pour les montants.
- Le texte peut déjà avoir des montants normalisés type 15575.000 (point = décimal millimes TND).
- Repère les libellés français / tunisiens: "N° FACTURE", "DATE DE LA FACTURE", "DELAIS DE PAIEMENT", "SOUS-TOTAL", "TOTAL TTC", "TTC", "HTVA", "TVA", "TIMBRE", "DROIT DE TIMBRE", "RESTE DU", "NET A PAYER", "CONCERNE", "M.F", "MATRICULE FISCAL".
- transaction_type = buy (achat): supplier_name = vendeur / émetteur de la facture; client_name = acheteur facturé (souvent STE ... ABBES ...). Ne pas mettre le client dans supplier_name.
- transaction_type = sell (vente): inverse logique si le texte le permet; sinon null + warning.
- Items: quantity, unit_price, line_subtotal doivent être cohérents (qté × PU ≈ sous-total ligne) avec les nombres visibles sur la ligne ou la ligne suivante.

Schéma JSON attendu (toutes les clés doivent exister; utiliser null si inconnu):
{
  "document_type": "invoice",
  "supplier_name": null,
  "supplier_full_name": null,
  "client_name": null,
  "invoice_number": null,
  "invoice_date": null,
  "payment_due_date": null,
  "client_tax_id": null,
  "supplier_tax_id": null,
  "currency": null,
  "items": [{"description": null, "details": null, "quantity": null, "unit_price": null, "line_subtotal": null}],
  "subtotal_amount": null,
  "tax_amount": null,
  "stamp_tax": null,
  "total_amount": null,
  "amount_paid": null,
  "remaining_due": null,
  "detected_labels": [],
  "missing_fields": [],
  "warnings": [],
  "field_confidence": {"supplier_name": 0, "client_name": 0, "invoice_number": 0, "invoice_date": 0, "total_amount": 0},
  "global_confidence": 0
}

Pour field_confidence (par champ) et global_confidence: nombres entre 0 et 1.
- Si la valeur est clairement lisible dans l'OCR (libellé proche, pas de contradiction), viser 0.75–0.95 pour ce champ.
- global_confidence: reflète l'ensemble (souvent 0.55–0.92 si la plupart des champs sont fiables).
- Ne pas artificiellement tout mettre bas si le texte suffit; ne pas surévaluer si le champ est ambigu ou absent.
Pas de texte hors JSON.
"""


def _unwrap_json_object(obj: dict[str, Any]) -> dict[str, Any]:
    for k in ("invoice", "result", "data", "extraction"):
        if k in obj and isinstance(obj[k], dict):
            inner = obj[k]
            if "document_type" in inner or "items" in inner:
                return inner
    return obj


def _parse_draft(raw: str) -> InvoiceExtractionDraft:
    s = (raw or "").strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", s)
        if not m:
            raise
        obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("LLM output not an object")
    obj = _unwrap_json_object(obj)
    return InvoiceExtractionDraft.model_validate(obj)


def _fallback_draft() -> InvoiceExtractionDraft:
    return InvoiceExtractionDraft(
        warnings=["LLM indisponible ou parse JSON échoué"],
        missing_fields=[
            "supplier_name",
            "invoice_number",
            "invoice_date",
            "total_amount",
            "currency",
        ],
        global_confidence=0.05,
    )


async def _call_llm_provider(provider: str, user: str) -> str:
    p = (provider or "").strip().lower()
    if p == "ollama":
        return await _ollama(user)
    if p == "openai":
        return await _openai(user)
    if p == "groq":
        return await _groq(user)
    if p == "mcp":
        return await _mcp(user)
    raise ValueError(f"unknown_or_unconfigured_llm_provider:{p}")


async def extract_invoice_with_llm(
    normalized_ocr_text: str,
    transaction_type: str,
) -> tuple[InvoiceExtractionDraft, str]:
    """
    Retourne (draft, raw_response_text).

    Chaîne : `LLM_PROVIDER` puis optionnellement `LLM_FALLBACK_PROVIDER` si échec réseau,
    réponse vide ou JSON invalide.
    """
    primary = (os.getenv("LLM_PROVIDER") or "groq").lower().strip()
    fallback = (os.getenv("LLM_FALLBACK_PROVIDER") or "").strip().lower()
    chain: list[str] = []
    for p in (primary, fallback):
        if p and p not in chain:
            chain.append(p)
    if not chain:
        chain = ["groq"]

    user = (
        f"TRANSACTION_TYPE: {transaction_type}\n\n"
        f"OCR_TEXT:\n{normalized_ocr_text}\n"
    )
    notes: list[str] = []
    last_raw = ""

    for prov in chain:
        if prov == "fallback":
            d = _fallback_draft()
            d.warnings = list({*(d.warnings or []), "LLM_PROVIDER=fallback"})
            return d, ""
        try:
            raw_out = await _call_llm_provider(prov, user)
            last_raw = raw_out or ""
        except Exception as e:
            msg = f"{prov}:{str(e)[:120]}"
            notes.append(msg)
            logger.warning("LLM provider %s call failed: %s", prov, str(e)[:300])
            continue
        if not (raw_out or "").strip():
            notes.append(f"{prov}:empty_response")
            continue
        try:
            draft = _parse_draft(raw_out)
            if prov != primary:
                draft.warnings = list(
                    {*(draft.warnings or []), f"llm_fallback_used:{prov}"}
                )
            return draft, raw_out
        except Exception as e:
            notes.append(f"{prov}:json_parse:{str(e)[:80]}")
            logger.warning("LLM provider %s JSON parse failed: %s", prov, str(e)[:200])
            continue

    logger.warning("All LLM providers exhausted: %s", notes[:5])
    d = _fallback_draft()
    d.warnings = list({*(d.warnings or []), *(notes[:5])})
    return d, last_raw


async def _ollama(user: str) -> str:
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    payload = {
        "model": model,
        "prompt": f"{INVOICE_GLOBAL_SYSTEM_PROMPT}\n\n{user}",
        "stream": False,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(f"{base}/api/generate", json=payload)
        r.raise_for_status()
    return str(r.json().get("response", "")).strip()


async def _openai(user: str) -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY missing")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": INVOICE_GLOBAL_SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
    data = r.json()
    return str(data.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()


async def _groq(user: str) -> str:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY missing")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": INVOICE_GLOBAL_SYSTEM_PROMPT},
            {"role": "user", "content": user},
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


async def _mcp(user: str) -> str:
    url = (os.getenv("EXTRACTION_MCP_URL") or "").strip()
    if not url:
        raise RuntimeError("EXTRACTION_MCP_URL missing")
    headers = {"Content-Type": "application/json"}
    try:
        extra = os.getenv("EXTRACTION_MCP_HEADERS")
        if extra:
            headers.update(json.loads(extra))
    except json.JSONDecodeError:
        pass
    # attend un service renvoyant le draft complet
    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post(
            url,
            json={"prompt": INVOICE_GLOBAL_SYSTEM_PROMPT, "user": user},
            headers=headers,
        )
        r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "raw" in data:
        return str(data["raw"])
    return json.dumps(data)


def heuristic_to_global_draft(heur: dict[str, Any]) -> InvoiceExtractionDraft:
    """Convertit la sortie heuristique legacy (`invoice_extraction`) en draft global."""
    items: list[InvoiceLineDraft] = []
    for it in heur.get("items") or []:
        if not isinstance(it, dict):
            continue
        items.append(
            InvoiceLineDraft(
                description=it.get("designation"),
                details=None,
                quantity=it.get("quantity"),
                unit_price=it.get("unit_price"),
                line_subtotal=it.get("line_total"),
            )
        )
    return InvoiceExtractionDraft(
        supplier_name=heur.get("supplier_name"),
        supplier_full_name=heur.get("supplier_name"),
        client_name=heur.get("client_name"),
        invoice_number=heur.get("invoice_number"),
        invoice_date=heur.get("invoice_date"),
        currency=heur.get("currency") or "TND",
        items=items,
        subtotal_amount=heur.get("subtotal_htva"),
        tax_amount=heur.get("tax_amount"),
        stamp_tax=heur.get("stamp_duty"),
        total_amount=heur.get("total_ttc"),
        warnings=[],
        missing_fields=[],
        global_confidence=0.52,
        field_confidence={
            "supplier_name": 0.55,
            "invoice_number": 0.55,
            "invoice_date": 0.55,
            "total_amount": 0.55,
            "client_name": 0.45,
        },
    )
