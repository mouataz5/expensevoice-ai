"""
LLaVA (ou modèle vision) via API Ollama locale — uniquement pour aide visuelle,
pas pour parser financièrement les tableaux.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx

from app.utils.image_to_base64 import image_file_to_base64

logger = logging.getLogger(__name__)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.I)


def is_ollama_vision_enabled() -> bool:
    return (os.getenv("OLLAMA_ENABLED") or "").strip().lower() in ("1", "true", "yes", "on")


def _ollama_base_url() -> str:
    return (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")


def _ollama_model() -> str:
    return (
        (os.getenv("OLLAMA_VISION_MODEL") or os.getenv("OLLAMA_MODEL") or "llava").strip() or "llava"
    )


def _ollama_timeout() -> float:
    try:
        return float(os.getenv("OLLAMA_TIMEOUT_SECONDS") or "120")
    except ValueError:
        return 120.0


def _parse_json_response(raw: str) -> dict[str, Any]:
    """Extrait un objet JSON depuis la sortie modèle (fences ou brut)."""
    raw = (raw or "").strip()
    if not raw:
        return {}
    m = _JSON_FENCE.search(raw)
    if m:
        raw = m.group(1).strip()
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else {}
    except json.JSONDecodeError:
        i, j = raw.find("{"), raw.rfind("}")
        if i >= 0 and j > i:
            try:
                out = json.loads(raw[i : j + 1])
                return out if isinstance(out, dict) else {}
            except json.JSONDecodeError:
                pass
    return {}


def ollama_chat_vision(image_path: str, user_prompt: str) -> tuple[str | None, str | None]:
    """
    Appelle POST /api/chat avec image base64. Retourne (content, error).
    """
    if not is_ollama_vision_enabled():
        return None, "ollama_disabled"
    path = Path(image_path)
    if not path.is_file():
        return None, "file_not_found"
    try:
        b64 = image_file_to_base64(path)
    except OSError as e:
        return None, f"read_error:{e!s}"[:120]

    url = f"{_ollama_base_url()}/api/chat"
    payload = {
        "model": _ollama_model(),
        "messages": [
            {
                "role": "user",
                "content": user_prompt,
                "images": [b64],
            }
        ],
        "stream": False,
        "options": {"temperature": 0.1},
    }
    try:
        with httpx.Client(timeout=_ollama_timeout()) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
        data = r.json()
        msg = data.get("message") or {}
        content = (msg.get("content") or "").strip()
        return (content, None) if content else (None, "empty_response")
    except httpx.TimeoutException:
        logger.warning("Ollama vision timeout model=%s", _ollama_model())
        return None, "timeout"
    except httpx.HTTPError as e:
        logger.warning("Ollama vision HTTP error: %s", e)
        return None, f"http_error:{e!s}"[:160]
    except Exception as e:
        logger.warning("Ollama vision unexpected: %s", e)
        return None, f"error:{e!s}"[:160]


def classify_document_type(image_path: str) -> dict[str, Any]:
    """
    Classification visuelle du type de document.
    Retour: detected_type, confidence, reasoning_short
    """
    prompt = """You are a careful document assistant. Look ONLY at this image.
Return ONLY valid JSON (no markdown):
{"detected_type":"invoice"|"quote"|"receipt"|"unknown","confidence":0.0,"reasoning_short":"max 100 chars"}
Rules:
- If you cannot read titles/headers confidently, use detected_type "unknown" and confidence <= 0.35.
- Do NOT invent document types not supported by visible layout/text.
- quote = estimate / quotation / devis / proforma style."""
    content, err = ollama_chat_vision(image_path, prompt)
    if err:
        return {"detected_type": "unknown", "confidence": 0.0, "reasoning_short": "", "error": err}
    data = _parse_json_response(content or "")
    return {
        "detected_type": str(data.get("detected_type") or "unknown").lower(),
        "confidence": float(data.get("confidence") or 0) if data.get("confidence") is not None else 0.0,
        "reasoning_short": str(data.get("reasoning_short") or "")[:200],
    }


def validate_header_blocks(image_path: str, ocr_result: Any) -> dict[str, Any]:
    """Vérification visuelle blocs en-tête vs indices OCR (sans les écraser)."""
    meta = {}
    raw_excerpt = ""
    if hasattr(ocr_result, "raw_text"):
        raw_excerpt = (ocr_result.raw_text or "")[:1800]
    elif isinstance(ocr_result, dict):
        raw_excerpt = str(ocr_result.get("raw_text") or "")[:1800]
    prompt = f"""Look at the image. OCR excerpt (may be wrong): \"\"\"{raw_excerpt}\"\"\"
Return ONLY JSON:
{{"supplier_present":true/false/null,"client_present":true/false/null,"date_present":true/false/null,
"tax_id_present":true/false/null,"hints":{{"supplier":"short or null","client":"short or null"}}}}
Use null if you cannot tell. Do NOT invent values not clearly visible. No markdown."""
    content, err = ollama_chat_vision(image_path, prompt)
    if err:
        return {
            "supplier_present": None,
            "client_present": None,
            "date_present": None,
            "tax_id_present": None,
            "hints": {},
            "error": err,
        }
    data = _parse_json_response(content or "")
    hints = data.get("hints") if isinstance(data.get("hints"), dict) else {}
    return {
        "supplier_present": data.get("supplier_present"),
        "client_present": data.get("client_present"),
        "date_present": data.get("date_present"),
        "tax_id_present": data.get("tax_id_present"),
        "hints": {k: (str(v)[:120] if v else None) for k, v in hints.items()},
    }


def validate_totals_block(image_path: str, extracted_totals: dict[str, Any]) -> dict[str, Any]:
    """Compare présence visuelle totaux vs chiffres extraits (avis seulement)."""
    tot = json.dumps(extracted_totals or {}, ensure_ascii=False)[:800]
    prompt = f"""Extracted totals JSON (from OCR pipeline, may be wrong): {tot}
Look at the image. Return ONLY JSON:
{{"totals_block_present":true/false/null,"visible_total_ttc":null,"visible_total_ht":null,"visible_tax":null,
"consistency_opinion":"agree"|"disagree"|"unclear"|null,"note":"max 120 chars"}}
Rules: Use null for any amount you cannot read exactly on the page. NEVER guess numbers. No markdown."""
    content, err = ollama_chat_vision(image_path, prompt)
    if err:
        return {
            "totals_block_present": None,
            "visible_total_ttc": None,
            "visible_total_ht": None,
            "visible_tax": None,
            "consistency_opinion": None,
            "note": "",
            "error": err,
        }
    data = _parse_json_response(content or "")
    return {
        "totals_block_present": data.get("totals_block_present"),
        "visible_total_ttc": data.get("visible_total_ttc"),
        "visible_total_ht": data.get("visible_total_ht"),
        "visible_tax": data.get("visible_tax"),
        "consistency_opinion": data.get("consistency_opinion"),
        "note": str(data.get("note") or "")[:200],
    }


def assess_manual_review_need(
    image_path: str,
    extraction_draft: dict[str, Any],
    validation_report: dict[str, Any],
) -> dict[str, Any]:
    """Décision assistance relecture humaine."""
    ctx = json.dumps(
        {"draft_excerpt": extraction_draft, "validation_excerpt": validation_report},
        ensure_ascii=False,
        default=str,
    )[:2500]
    prompt = f"""Context (JSON): {ctx}
Look at the image. Return ONLY JSON:
{{"manual_review_required":true/false,"reason_codes":[],"summary_for_user":"French max 200 chars","confidence_adjustment":0.0}}
confidence_adjustment: add between -0.25 and 0.1 to trust (negative = less trust). Do not claim exact amounts.
If table line items look unreliable or unreadable, set manual_review_required true.
No markdown."""
    content, err = ollama_chat_vision(image_path, prompt)
    if err:
        return {
            "manual_review_required": False,
            "reason_codes": [],
            "summary_for_user": "",
            "confidence_adjustment": 0.0,
            "error": err,
        }
    data = _parse_json_response(content or "")
    try:
        adj = float(data.get("confidence_adjustment") or 0.0)
    except (TypeError, ValueError):
        adj = 0.0
    adj = max(-0.25, min(0.1, adj))
    codes = data.get("reason_codes")
    if not isinstance(codes, list):
        codes = []
    return {
        "manual_review_required": bool(data.get("manual_review_required")),
        "reason_codes": [str(c)[:80] for c in codes[:12]],
        "summary_for_user": str(data.get("summary_for_user") or "")[:240],
        "confidence_adjustment": adj,
    }


def run_combined_visual_audit(
    image_path: str,
    *,
    ocr_excerpt: str,
    draft_summary: dict[str, Any],
    validation_summary: dict[str, Any],
) -> dict[str, Any]:
    """
    Un seul appel visuel pour limiter la latence (classification + entêtes + totaux + relecture).
    Utilisé par le pipeline lorsque les garde-fous demandent LLaVA.
    """
    payload = json.dumps(
        {
            "ocr_text_excerpt": ocr_excerpt[:2000],
            "draft": draft_summary,
            "validation": validation_summary,
        },
        ensure_ascii=False,
        default=str,
    )
    prompt = f"""You verify scanned business documents. Context JSON:
{payload}

Look at the IMAGE only for visual facts. Return ONE JSON object (no markdown), shape:
{{
  "document": {{
    "detected_type": "invoice"|"quote"|"receipt"|"unknown",
    "type_confidence": 0.0,
    "reasoning_short": "max 80 chars"
  }},
  "headers": {{
    "supplier_visible": true/false/null,
    "client_visible": true/false/null,
    "date_visible": true/false/null,
    "tax_id_visible": true/false/null
  }},
  "totals": {{
    "totals_block_visible": true/false/null,
    "visible_ttc": null,
    "visible_ht": null,
    "visible_tax": null,
    "compare_note": "max 80 chars or null"
  }},
  "review": {{
    "manual_review_required": true/false,
    "reason_codes": [],
    "summary_for_user": "French max 200 chars",
    "confidence_delta": -0.25 to 0.1
  }}
}}
STRICT: null for any field you cannot read clearly. NEVER invent numbers. NEVER output line-item tables.
If uncertain, use null or unknown and low confidence."""
    content, err = ollama_chat_vision(image_path, prompt)
    if err:
        return {"skipped": True, "error": err}
    data = _parse_json_response(content or "")
    if not data:
        return {"skipped": True, "error": "parse_failed", "raw_excerpt": (content or "")[:400]}
    return {"skipped": False, "audit": data}


__all__ = [
    "assess_manual_review_need",
    "classify_document_type",
    "is_ollama_vision_enabled",
    "ollama_chat_vision",
    "run_combined_visual_audit",
    "validate_header_blocks",
    "validate_totals_block",
]
