"""
Extraction service — LLM extraction with transaction_type, validation, no hallucination.
Part 2: Pass transaction_type (sell/buy); improved prompt; structured validation.
Part 6: Clean architecture; extraction logic lives here.
"""
import json
import logging
import os
from typing import Any

import httpx

from app.schemas.extraction import ExtractedPurchase

logger = logging.getLogger(__name__)

EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "product_name": {"type": "string"},
        "category": {
            "type": "string",
            "enum": [
                "vente_poulet",
                "achat_aliment",
                "materiel",
                "transport",
                "autre",
            ],
        },
        "quantity": {"type": "integer", "minimum": 1},
        "unit_price": {"type": "number", "minimum": 0},
        "total_amount": {"type": "number", "minimum": 0},
        "currency": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "notes": {"type": ["string", "null"]},
    },
    "required": [
        "product_name",
        "category",
        "quantity",
        "unit_price",
        "total_amount",
        "currency",
        "confidence",
    ],
}


def build_system_prompt(transaction_type: str | None) -> str:
    """Part 2: Prompt with transaction_type; never hallucinate; Tunisian dialect; server computes total."""
    t = (transaction_type or "buy").lower()
    type_ar = "بيع (sell)" if t == "sell" else "شراء (buy)"
    return f"""You extract structured purchase/sale information from a voice transcription.
The company is a chicken farm/sales business in Tunisia.
This transaction is: {type_ar}.

Rules:
- Return ONLY valid JSON matching the schema. No markdown, no explanation.
- Do NOT invent data. If something is missing or unclear, use reasonable defaults and SET confidence BELOW 0.7.
- For numbers: only use what is clearly stated. If unclear, use quantity=1, unit_price=0 and set confidence low.
- Recognise Tunisian dialect and Arabic/French mix (دينار, كيلو, كغ, لتر, علبة, قنطار, etc.).
- total_amount in JSON will be IGNORED; server always computes total_amount = quantity * unit_price.
- Categories: vente_poulet, achat_aliment, materiel, transport, autre.
- If unsure about category, use "autre" and lower confidence.
"""


def _provider() -> str:
    return os.getenv("LLM_PROVIDER", "ollama").lower()


async def extract_with_ollama(
    transcription: str,
    transaction_type: str | None = None,
) -> ExtractedPurchase:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
    system = build_system_prompt(transaction_type)
    prompt = f"{system}\n\nTRANSCRIPTION:\n{transcription}\n"
    payload = {"model": model, "prompt": prompt, "stream": False, "format": "json"}
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{base_url}/api/generate", json=payload)
        r.raise_for_status()
        data = r.json()
    raw = data.get("response", "").strip()
    obj = json.loads(raw)
    return ExtractedPurchase(**obj)


async def extract_with_openai(
    transcription: str,
    transaction_type: str | None = None,
) -> ExtractedPurchase:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    system = build_system_prompt(transaction_type)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"TRANSCRIPTION:\n{transcription}\n"},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "purchase_extraction",
                "strict": True,
                "schema": EXTRACTION_JSON_SCHEMA,
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
    obj = json.loads(content)
    return ExtractedPurchase(**obj)


async def extract_with_groq(
    transcription: str,
    transaction_type: str | None = None,
) -> ExtractedPurchase:
    """Extract using Groq API (OpenAI-compatible). Uses JSON mode for reliable output."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY missing")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    system = build_system_prompt(transaction_type)
    schema_hint = json.dumps(EXTRACTION_JSON_SCHEMA, ensure_ascii=False)
    user_content = (
        f"TRANSCRIPTION:\n{transcription}\n\n"
        f"Return ONLY a JSON object matching this schema:\n{schema_hint}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    if not content:
        raise RuntimeError("Groq response missing content")
    obj = json.loads(content)
    # Provide safe defaults for any missing fields
    obj.setdefault("product_name", "inconnu")
    obj.setdefault("category", "autre")
    obj.setdefault("quantity", 1)
    obj.setdefault("unit_price", 0.0)
    obj.setdefault("total_amount", 0.0)
    obj.setdefault("currency", "TND")
    obj.setdefault("confidence", 0.5)
    return ExtractedPurchase(**obj)


async def extract_purchase_fields(
    transcription: str,
    transaction_type: str | None = None,
) -> ExtractedPurchase:
    """Extract with transaction_type; used by API and by purchase_processing."""
    prov = _provider()
    if prov == "ollama":
        return await extract_with_ollama(transcription, transaction_type)
    if prov == "openai":
        return await extract_with_openai(transcription, transaction_type)
    if prov == "groq":
        return await extract_with_groq(transcription, transaction_type)
    raise RuntimeError(f"Unknown LLM_PROVIDER: {prov}")


def validate_and_sanitize(
    extracted: ExtractedPurchase,
    allowed_categories: list[str] | None,
) -> tuple[int, float, float, float]:
    """
    Part 2: Structured validation.
    Returns (quantity, unit_price, total_amount, confidence).
    - quantity > 0
    - unit_price >= 0
    - category in allowed list (or first allowed / autre)
    - total_amount = quantity * unit_price (server-side).
    """
    qty = max(1, int(extracted.quantity) if extracted.quantity is not None else 1)
    price = max(0.0, float(extracted.unit_price) if extracted.unit_price is not None else 0.0)
    total = round(qty * price, 3)
    conf = max(0.0, min(1.0, float(extracted.confidence) if extracted.confidence is not None else 0.5))
    if allowed_categories and extracted.category and extracted.category not in allowed_categories:
        # Keep category but could force to autre; for now keep and let confirm reject if needed
        conf = min(conf, 0.6)
    return qty, price, total, conf
