"""
Invoice extraction service using LLM to parse OCR text and extract structured data.

Extracts invoice fields from OCR text in Tunisian/French/Arabic invoices.
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# JSON schema for invoice extraction
INVOICE_EXTRACTION_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "supplier_name": {"type": "string"},
        "invoice_number": {"type": "string"},
        "invoice_date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$|^$"},  # YYYY-MM-DD
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "designation": {"type": "string"},
                    "quantity": {"type": "number", "minimum": 0},
                    "unit_price": {"type": "number", "minimum": 0},
                    "line_total": {"type": "number", "minimum": 0}
                },
                "required": ["designation", "quantity", "unit_price", "line_total"]
            }
        },
        "subtotal_htva": {"type": "number", "minimum": 0},
        "tax_amount": {"type": "number", "minimum": 0},
        "total_ttc": {"type": "number", "minimum": 0},
        "currency": {"type": "string", "enum": ["TND", "EUR", "USD", "DZD", "MAD", "SAR", "AED", "EGP", ""]}
    },
    "required": ["items", "currency"]
}

# System prompt for invoice extraction
INVOICE_SYSTEM_PROMPT = """\
Extract invoice data from Arabic/French text (Tunisian context). Output ONLY valid JSON.

Common Tunisian/French terms: FACTURE=invoice, BON DE LIVRAISON=delivery note, 
FOURNISSEUR=supplier, CLIENT=customer, DESIGNATION=product description,
QUANTITÉ=quantity, PRIX UNITAIRE=unit price, TOTAL LIGNE=line total,
SOUS-TOTAL=subtotal (HTVA), TVA=tax, TOTAL TTC=total with tax,
DEN=دينار (TND), EUROS=euros (EUR), DOLLARS=dollars (USD)

Output format: {
  "supplier_name": "string",
  "invoice_number": "string", 
  "invoice_date": "YYYY-MM-DD",
  "items": [{"designation": "string", "quantity": number, "unit_price": number, "line_total": number}],
  "subtotal_htva": number,
  "tax_amount": number, 
  "total_ttc": number,
  "currency": "TND|EUR|USD|..."
}

Rules: If value unclear → use null. Never hallucinate numbers. No markdown, no text before/after JSON.
"""

# JSON parsing helpers
INVOICE_FIELDS = {"supplier_name", "invoice_number", "invoice_date", "items", "subtotal_htva", "tax_amount", "total_ttc", "currency"}


def _unwrap_llm_obj(obj: Dict) -> Dict:
    """
    Some models wrap the result inside a list or dict key.
    e.g. {"invoice": {...}} or {"result": {...}}
    Detect and unwrap one level when the inner object has invoice fields.
    """
    WRAPPER_KEYS = (
        "invoice", "result", "data", "document", "extraction", 
        "output", "response", "parsed", "extracted"
    )
    # List wrapper: {"invoices": [{...}]}
    for v in obj.values():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            candidate = v[0]
            if INVOICE_FIELDS & set(candidate.keys()):
                return candidate
    # Dict wrapper: {"invoice": {...}}
    for k in WRAPPER_KEYS:
        if k in obj and isinstance(obj[k], dict):
            candidate = obj[k]
            if INVOICE_FIELDS & set(candidate.keys()):
                return candidate
    return obj


def _parse_json_from_response(raw: str) -> Dict:
    """Parse and normalize the first JSON object found in an LLM response."""
    raw = raw.strip()
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"No valid JSON in LLM response: {raw[:300]!r}")
        obj = json.loads(match.group())

    return _unwrap_llm_obj(obj)


def _apply_invoice_defaults(obj: Dict) -> Dict:
    """Apply safe fallback values for missing fields."""
    obj.setdefault("supplier_name", "")
    obj.setdefault("invoice_number", "")
    obj.setdefault("invoice_date", "")
    obj.setdefault("subtotal_htva", 0.0)
    obj.setdefault("tax_amount", 0.0)
    obj.setdefault("total_ttc", 0.0)
    obj.setdefault("currency", "TND")
    
    # Ensure items is a list
    if "items" not in obj or not isinstance(obj["items"], list):
        obj["items"] = []
    
    # Validate and clean items
    cleaned_items = []
    for item in obj.get("items", []):
        if isinstance(item, dict):
            item.setdefault("designation", "")
            item.setdefault("quantity", 0)
            item.setdefault("unit_price", 0.0)
            item.setdefault("line_total", 0.0)
            # Recalculate line total if needed
            if item["quantity"] and item["unit_price"]:
                item["line_total"] = round(item["quantity"] * item["unit_price"], 3)
            cleaned_items.append(item)
    
    obj["items"] = cleaned_items
    
    return obj


def _fallback_invoice_extraction(ocr_text: str) -> Dict:
    """Return safe defaults when LLM output is invalid."""
    return {
        "supplier_name": "",
        "invoice_number": "",
        "invoice_date": "",
        "items": [],
        "subtotal_htva": 0.0,
        "tax_amount": 0.0,
        "total_ttc": 0.0,
        "currency": "TND",
        "extraction_error": "Failed to parse invoice - manual review required"
    }


async def _extract_invoice_ollama(ocr_text: str, transaction_type: str) -> Dict:
    """Extract invoice fields using Ollama."""
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "aya:8b")

    prompt = (
        f"{INVOICE_SYSTEM_PROMPT}\n"
        f"TRANSACTION TYPE: {transaction_type}\n"
        f"OCR TEXT:\n{ocr_text}\n"
    )

    # Configure generation parameters for accuracy
    num_predict = int(os.getenv("LLM_NUM_PREDICT", "320"))
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    options = {
        "num_predict": num_predict,
        "temperature": temperature,
        "top_p": 0.9,
        "repeat_penalty": 1.1,
    }

    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": options,
            },
        )
        r.raise_for_status()

    raw = r.json().get("response", "").strip()
    logger.debug("Ollama invoice extraction raw response → %s", raw[:400])
    try:
        obj = _apply_invoice_defaults(_parse_json_from_response(raw))
        return obj
    except (ValueError, KeyError, TypeError) as e:
        logger.warning("Ollama invoice extraction parse failed (%s), using fallback", e)
        return _fallback_invoice_extraction(ocr_text)


async def _extract_invoice_openai(ocr_text: str, transaction_type: str) -> Dict:
    """Extract invoice fields using OpenAI."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    user_content = f"TRANSACTION TYPE: {transaction_type}\nOCR TEXT:\n{ocr_text}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": INVOICE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "invoice_extraction",
                "strict": True,
                "schema": INVOICE_EXTRACTION_JSON_SCHEMA,
            },
        },
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        r.raise_for_status()

    content = (
        r.json()
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content")
    )
    if not content:
        raise RuntimeError("OpenAI returned empty content")
    try:
        obj = _apply_invoice_defaults(json.loads(content))
        return obj
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        logger.warning("OpenAI invoice extraction parse failed (%s), using fallback", e)
        return _fallback_invoice_extraction(ocr_text)


async def _extract_invoice_mcp(ocr_text: str, transaction_type: str) -> Dict:
    """
    Call EXTRACTION_MCP_URL with POST {"ocr_text": "...", "transaction_type": "sell"|"buy"}.
    Response must be JSON with invoice fields.
    """
    url = os.getenv("EXTRACTION_MCP_URL", "").strip()
    if not url:
        raise RuntimeError("EXTRACTION_MCP_URL is not set when using LLM_PROVIDER=mcp")
    
    payload = {"ocr_text": ocr_text, "transaction_type": transaction_type}
    headers = {"Content-Type": "application/json"}
    
    try:
        extra = os.getenv("EXTRACTION_MCP_HEADERS")
        if extra:
            headers.update(json.loads(extra))
    except json.JSONDecodeError:
        pass
    
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
    
    data = r.json()
    if not isinstance(data, dict):
        return _fallback_invoice_extraction(ocr_text)
    
    obj = _apply_invoice_defaults(_unwrap_llm_obj(data))
    return obj


async def _extract_invoice_groq(ocr_text: str, transaction_type: str) -> Dict:
    """Extract invoice fields using Groq."""
    from groq import Groq
    import os
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    client = Groq(api_key=api_key)
    
    user_content = f"TRANSACTION TYPE: {transaction_type}\nOCR TEXT:\n{ocr_text}"
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": INVOICE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            model=model,
            response_format={"type": "json_object"},  # Request JSON format
        )
        
        content = chat_completion.choices[0].message.content
        if not content:
            raise RuntimeError("Groq returned empty content")
        
        obj = _apply_invoice_defaults(json.loads(content))
        return obj
    except Exception as e:
        logger.warning("Groq invoice extraction failed (%s), using fallback", e)
        return _fallback_invoice_extraction(ocr_text)


async def extract_invoice_fields(ocr_text: str, transaction_type: str) -> Dict:
    """
    Extract structured invoice fields from OCR text using LLM.
    
    transaction_type: "sell" | "buy" — context for better accuracy.
    Provider: LLM_PROVIDER env var (ollama | openai | mcp | groq | fallback).
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    
    try:
        if provider == "ollama":
            return await _extract_invoice_ollama(ocr_text, transaction_type)
        elif provider == "openai":
            return await _extract_invoice_openai(ocr_text, transaction_type)
        elif provider == "mcp":
            try:
                return await _extract_invoice_mcp(ocr_text, transaction_type)
            except Exception as e:
                logger.warning("MCP invoice extraction failed (%s), using fallback", e)
                return _fallback_invoice_extraction(ocr_text)
        elif provider == "groq":
            return await _extract_invoice_groq(ocr_text, transaction_type)
        elif provider == "fallback":
            # Return a simple fallback when no LLM provider is configured
            logger.info("Using fallback extraction (no LLM provider configured)")
            return _apply_invoice_defaults({
                "items": [],
                "currency": "TND",
                "extraction_method": "fallback_due_to_no_provider"
            })
        else:
            raise RuntimeError(f"Unknown LLM_PROVIDER: {provider!r}")
    except Exception as e:
        logger.error(f"LLM extraction failed for provider {provider}: {e}")
        # Check if this is an import error (missing dependencies) and provide appropriate fallback
        if provider == "ollama":
            logger.warning("Ollama not available, likely missing dependencies. Using fallback.")
        elif provider == "groq":
            logger.warning("Groq not available, likely missing dependencies. Using fallback.")
        elif provider == "openai":
            logger.warning("OpenAI not available, likely missing dependencies. Using fallback.")
        
        # Always return a safe fallback instead of failing completely
        return _fallback_invoice_extraction(ocr_text)
