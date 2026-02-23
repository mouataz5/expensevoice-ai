import json
import os
from typing import Any

import httpx

from app.schemas.extraction import ExtractedPurchase

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

SYSTEM_RULES = """You extract structured purchase/sale information from a transcription.
The company is a chicken farm/sales business in Tunisia.
Languages can be Tunisian Arabic, Arabic, French, or English.
Return ONLY valid JSON matching the schema.
If missing info, make best estimate and lower confidence.
Compute total_amount = quantity * unit_price when possible.
"""


def _provider() -> str:
    return os.getenv("LLM_PROVIDER", "ollama").lower()


async def extract_with_ollama(transcription: str) -> ExtractedPurchase:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip(
        "/"
    )
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")

    prompt = f"{SYSTEM_RULES}\n\nTRANSCRIPTION:\n{transcription}\n"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{base_url}/api/generate", json=payload)
        r.raise_for_status()
        data = r.json()

    raw = data.get("response", "").strip()
    obj = json.loads(raw)
    return ExtractedPurchase(**obj)


async def extract_with_openai(transcription: str) -> ExtractedPurchase:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_RULES},
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

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

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


async def extract_purchase_fields(transcription: str) -> ExtractedPurchase:
    prov = _provider()
    if prov == "ollama":
        return await extract_with_ollama(transcription)
    if prov == "openai":
        return await extract_with_openai(transcription)
    raise RuntimeError(f"Unknown LLM_PROVIDER: {prov}")
