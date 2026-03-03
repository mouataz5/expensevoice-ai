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


def _parse_tnd_amount(raw: str) -> float | None:
    """
    Parse Tunisian amount notation into a float.
    Tunisian format: dots or commas as thousands separators, 3 decimal places (millimes).
    Examples: "15.575.000" → 15575.0, "22 176,003" → 22176.003, "1.000" → 1.0
    """
    import re
    cleaned = raw.strip().replace(" ", "").replace("\u00a0", "")
    cleaned = re.sub(r"[^\d.,]", "", cleaned)
    if not cleaned:
        return None

    dot_parts = cleaned.split(".")
    if len(dot_parts) >= 3 and all(len(p) == 3 for p in dot_parts[1:]):
        integer_part = "".join(dot_parts[:-1])
        decimal_part = dot_parts[-1]
        try:
            return float(f"{integer_part}.{decimal_part}")
        except ValueError:
            pass

    comma_parts = cleaned.split(",")
    if len(comma_parts) >= 3 and all(len(p) == 3 for p in comma_parts[1:]):
        integer_part = "".join(comma_parts[:-1])
        decimal_part = comma_parts[-1]
        try:
            return float(f"{integer_part}.{decimal_part}")
        except ValueError:
            pass

    if "," in cleaned and "." in cleaned:
        if cleaned.rindex(",") > cleaned.rindex("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[-1]) == 3:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) == 2 and len(parts[-1]) == 3:
            pass
        elif len(parts) == 2 and len(parts[-1]) != 3:
            pass

    try:
        return float(cleaned)
    except ValueError:
        return None


# Patterns for Tunisian amounts: "15.575.000" or "22 176,003" or "15,575,000"
_TND_AMOUNT_PATTERNS = [
    r"(?<!\d)\d{1,3}(?:\.\d{3}){2,}(?!\d)",   # 15.575.000 (dot thousands + millimes)
    r"(?<!\d)\d{1,3}(?:,\d{3}){2,}(?!\d)",     # 15,575,000 (comma thousands + millimes)
    r"(?<!\d)\d{1,3}(?:\s\d{3})+[.,]\d{3}(?!\d)",  # 22 176,003 (space thousands)
    r"(?<!\d)\d+[.,]\d{3}(?!\d)",               # 22176,003 or 22176.003 (simple decimal)
]


def _find_tnd_amounts(text: str) -> list[float]:
    """Find all Tunisian-formatted amounts in text."""
    import re
    result = []
    seen_positions: set[int] = set()
    for pat in _TND_AMOUNT_PATTERNS:
        for m in re.finditer(pat, text):
            if m.start() in seen_positions:
                continue
            seen_positions.add(m.start())
            val = _parse_tnd_amount(m.group())
            if val is not None and val > 0:
                result.append(val)
    return result


def _regex_fallback(ocr_text: str) -> dict:
    """Best-effort extraction using regex when LLM is unavailable."""
    import re

    text = ocr_text
    lines = text.split("\n")
    supplier = None
    invoice_number = None
    invoice_date = None
    htva = None
    tva = None
    ttc = None

    supplier_patterns = [
        (r"SOCIETE\s*[:\-]?\s*\n?\s*(.+?)(?:\n|$)", 1),
        (r"(SOCIET[EÉ]\s+[A-Z\s]+(?:STPA|SA|SARL|SUARL|SOCEP)[A-Z\s]*)", 1),
        (r"(SOC\w*ET\w*\s*[:\-]?\s*\n?\s*.+?)(?:\n|$)", 1),
        (r"(SOCEP\b.*?)(?:\n|$)", 1),
        (r"(STE\s+DE\s+.+?)(?:\n|$)", 1),
        (r"(SOC\w{2,}\s+.+?)(?:\n|$)", 1),
        (r"(الشركة\s+.+?)(?:\n|$)", 1),
        (r"(?:المورد|Fournisseur)\s*[:\-]?\s*(.+)", 1),
    ]
    for pat, grp in supplier_patterns:
        m = re.search(pat, text, re.I | re.M)
        if m:
            val = m.group(grp).strip()
            val = re.sub(r"[|_\-=]+$", "", val).strip()
            if len(val) > 3:
                supplier = val[:120]
                break

    for pat in [
        r"(FA\d{2,}[/\-]\d{2,4})",
        r"FAC[_\-]?\s*([\w\d/\-]+)",
        r"N[°o]\s*(?:FACTURE)?\s*\n?\s*(FA?\d[\w/\-]+)",
        r"Facture\s*[:\-]?\s*\n?\s*([A-Z0-9\-/]+)",
    ]:
        m = re.search(pat, text, re.I | re.M)
        if m:
            val = m.group(1).strip()[:30]
            if len(val) >= 3 and re.search(r"\d", val):
                invoice_number = val
                break

    m = re.search(r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", text)
    if m:
        invoice_date = m.group(1)

    def _labeled_amount(label: str) -> float | None:
        """Find an amount on the same line or next line after a label."""
        for i, line in enumerate(lines):
            if re.search(label, line, re.I):
                amounts = _find_tnd_amounts(line)
                if amounts:
                    return max(amounts)
                if i + 1 < len(lines):
                    amounts = _find_tnd_amounts(lines[i + 1])
                    if amounts:
                        return max(amounts)
        return None

    htva = (
        _labeled_amount(r"TOTAL\s+HTVA") or _labeled_amount("HTVA")
        or _labeled_amount("SOUS.TOTAL") or _labeled_amount("SOUS-TOTAL")
    )
    tva = _labeled_amount(r"TOTAL\s+TVA") or _labeled_amount(r"TAXE\s+TIMBRE")
    ttc = (
        _labeled_amount(r"TOTAL\s+TTC") or _labeled_amount("TTC")
        or _labeled_amount("PAIMENTS?\s+RECUS?") or _labeled_amount("MONTANT\s+TOTAL")
    )

    if not ttc:
        all_amounts = _find_tnd_amounts(text)
        if all_amounts:
            ttc = max(all_amounts)

    if not ttc:
        space_nums = re.findall(r"(?<!\d)(\d{1,3}(?:\s\d{3})+)(?!\d)", text)
        candidates = []
        for sn in space_nums:
            val = _parse_tnd_amount(sn)
            if val and val > 100:
                candidates.append(val)
        if candidates:
            ttc = max(candidates)

    items: list[dict] = []
    skip_labels = re.compile(
        r"sous.total|total|htva|ttc|tva|timbre|paiment|facture|delais|concerne|"
        r"assiette|droit|taux|arrêt|vingt|mille|poids|remise|reste",
        re.I,
    )
    for line in lines:
        if skip_labels.search(line):
            continue
        amounts = _find_tnd_amounts(line)

        clean_line = line
        for pat in _TND_AMOUNT_PATTERNS:
            clean_line = re.sub(pat, " ", clean_line)
        plain_ints = re.findall(r"(?<!\d)(\d{2,6})(?!\d)", clean_line)
        plain_vals = []
        for pi in plain_ints:
            try:
                v = float(pi)
                if 1 < v < 1_000_000:
                    plain_vals.append(v)
            except ValueError:
                pass

        all_nums = plain_vals + amounts
        if len(all_nums) >= 2 and amounts:
            desig_part = re.split(r"\d", line, maxsplit=1)[0].strip()
            if not desig_part or len(desig_part) < 3:
                desig_part = re.sub(r"[\d\s.,|]+", " ", line).strip()[:80]
            alpha_count = sum(1 for c in desig_part if c.isalpha())
            if alpha_count >= 3:
                best_total = max(amounts)
                if plain_vals and len(plain_vals) >= 2:
                    plain_vals.sort()
                    def _check_match(pu: float, qty: float, total: float) -> bool:
                        for divisor in (1, 1000):
                            expected = (pu * qty) / divisor
                            if abs(expected - total) < total * 0.05:
                                return True
                        return False
                    pu_a, qty_a = plain_vals[0], plain_vals[-1]
                    pu_b, qty_b = plain_vals[-1], plain_vals[0]
                    if _check_match(pu_a, qty_a, best_total):
                        unit_price, quantity = pu_a, qty_a
                    elif _check_match(pu_b, qty_b, best_total):
                        unit_price, quantity = pu_b, qty_b
                    else:
                        unit_price, quantity = plain_vals[0], plain_vals[-1]
                elif plain_vals:
                    unit_price = plain_vals[0]
                    quantity = round(best_total / unit_price) if unit_price else 1
                else:
                    unit_price = best_total
                    quantity = 1

                items.append({
                    "designation": desig_part.strip()[:60],
                    "quantity": quantity or 1,
                    "unit_price": unit_price or best_total,
                    "line_total": best_total,
                })

    found_count = sum([bool(supplier), bool(invoice_number), bool(ttc), len(items) > 0])
    confidence = min(0.65, 0.16 * found_count) if found_count else 0.05

    return {
        "supplier_name": supplier,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "currency": "TND",
        "items": items[:20],
        "totals": {"htva": htva, "tva": tva, "ttc": ttc},
        "confidence": confidence,
    }


async def extract_invoice_from_ocr(ocr_text: str, transaction_type: str) -> tuple[dict, float]:
    """
    Extract structured invoice JSON from OCR text.
    Priority: LLM (Ollama/OpenAI) → regex fallback.
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
    try:
        if prov == "ollama":
            obj = await _extract_with_ollama(ocr_text, transaction_type)
        elif prov == "openai":
            obj = await _extract_with_openai(ocr_text, transaction_type)
        else:
            raise RuntimeError(f"Unknown LLM_PROVIDER: {prov}")
        conf = float(obj.get("confidence", 0.5))
        return obj, max(0.0, min(1.0, conf))
    except Exception as e:
        logger.warning("LLM extraction failed, using regex fallback: %s", e)
        obj = _regex_fallback(ocr_text)
        conf = float(obj.get("confidence", 0.1))
        return obj, conf
