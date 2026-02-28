"""
Invoice extraction — LLM extracts structured data from OCR text.
Tunisian invoices: French + Arabic; FACTURE, HTVA, TVA, TTC, etc.
Output: supplier_name, invoice_number, invoice_date, items[], totals, currency.
"""
import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

INVOICE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "supplier_name": {"type": ["string", "null"]},
        "invoice_number": {"type": ["string", "null"]},
        "invoice_date": {"type": ["string", "null"]},
        "currency": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "designation": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit_price": {"type": "number"},
                    "line_total": {"type": "number"},
                },
                "required": ["designation", "quantity", "unit_price", "line_total"],
            },
        },
        "totals": {
            "type": "object",
            "properties": {
                "htva": {"type": ["number", "null"]},
                "tva": {"type": ["number", "null"]},
                "ttc": {"type": ["number", "null"]},
            },
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["supplier_name", "invoice_number", "invoice_date", "currency", "items", "totals", "confidence"],
}

SYSTEM_PROMPT = """You extract structured invoice data from OCR text. Tunisian invoices often use French and Arabic.
Keywords: FACTURE, BON DE LIVRAISON, BON DE COMMANDE, HTVA, TVA, TTC, Montant, Quantité, Prix unitaire, Total.
Arabic: فاتورة، رقم، تاريخ، المورد، الإجمالي.

Rules:
- Return ONLY valid JSON. No markdown, no explanation.
- Do NOT invent data. If a field is missing or unclear, set it to null and lower confidence (below 0.7).
- supplier_name: vendor/supplier name. invoice_number: number on invoice. invoice_date: ISO date or null.
- items: array of line items with designation, quantity, unit_price, line_total.
- totals: htva (HT), tva (TVA amount), ttc (TTC total). Use null if not found.
- currency: usually TND for Tunisia.
- confidence: 0-1. Lower if unsure or many nulls.
"""


def _provider() -> str:
    return os.getenv("LLM_PROVIDER", "ollama").lower()


async def _extract_with_ollama(ocr_text: str, transaction_type: str) -> dict:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
    prompt = f"{SYSTEM_PROMPT}\n\nTransaction type: {transaction_type}\n\nOCR TEXT:\n{ocr_text}\n"
    payload = {"model": model, "prompt": prompt, "stream": False, "format": "json"}
    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(f"{base_url}/api/generate", json=payload)
        r.raise_for_status()
        data = r.json()
    raw = data.get("response", "").strip()
    return json.loads(raw)


async def _extract_with_openai(ocr_text: str, transaction_type: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Transaction: {transaction_type}\n\nOCR TEXT:\n{ocr_text}\n"},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "invoice_extraction",
                "strict": True,
                "schema": INVOICE_JSON_SCHEMA,
            },
        },
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError("OpenAI response missing content")
    return json.loads(content)


async def extract_invoice_from_ocr(ocr_text: str, transaction_type: str) -> tuple[dict, float]:
    """
    Extract structured invoice JSON from OCR text.
    Returns (extracted_dict, confidence).
    """
    if not ocr_text or not ocr_text.strip():
        return {
            "supplier_name": None,
            "invoice_number": None,
            "invoice_date": None,
            "currency": "TND",
            "items": [],
            "totals": {"htva": None, "tva": None, "ttc": None},
            "confidence": 0.0,
        }, 0.0

    prov = _provider()
    if prov == "ollama":
        obj = await _extract_with_ollama(ocr_text, transaction_type)
    elif prov == "openai":
        obj = await _extract_with_openai(ocr_text, transaction_type)
    else:
        raise RuntimeError(f"Unknown LLM_PROVIDER: {prov}")

    conf = float(obj.get("confidence", 0.5))
    return obj, max(0.0, min(1.0, conf))
