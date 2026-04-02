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
Extract structured invoice data from OCR text of Tunisian/French invoices.
Output ONLY valid JSON — no markdown, no text before or after.

=== CRITICAL: SUPPLIER vs CLIENT ===
The SUPPLIER (supplier_name) is the company AT THE TOP of the invoice — in the letterhead, logo area, or header.
The CLIENT is the company RECEIVING the invoice — listed after "CLIENT:", "SOCIETE:", "DESTINATAIRE:", "ACHETEUR:".
NEVER use the CLIENT/SOCIETE/DESTINATAIRE field as supplier_name.
Examples:
  "SOCEP STE DE CENTRE DES POUSSINS" at top with logo          → SUPPLIER ✓
  "ACN / Société Les Aliments Composés du Nord" in header       → SUPPLIER ✓
  "STPA / SOCIETE TUNISIENNE DE PRODUCTION ALIMENTAIRE" header  → SUPPLIER ✓
  "TAHAR TLILI / USINE D'ALIMENTS" at top                       → SUPPLIER ✓
  "Société Medimix / alfa NUTRITION ANIMALE" in header          → SUPPLIER ✓
  "STE ABBES POUR VOLAILLE" after "CLIENT:" or "SOCIETE:"       → CLIENT — NOT supplier ✗

=== INVOICE DOCUMENT TERMS ===
N° FACTURE / FACTURE / N FACTURE = invoice number
BON DE LIVRAISON / BL / LIV- = delivery note number → use as invoice_number
DATE / DATE DE LA FACTURE = invoice date (use this, not MAJ date, not payment date)

=== ITEM TABLE COLUMNS ===
DESIGNATION / ARTICLE / LIBELLE / PRODUIT = item description
QTE / QUANTITE / HRS/QTE / Qté / Nbr = quantity (number)
UNITE / U = unit of measure (Tonne, Sac, etc.) — do NOT extract as quantity
PRIX UNITAIRE / P.U / PU.HT / P.U.H.T / P.U. Net Remise = unit price (TND, after discount)
MONTANT / MONTANT HT / SOUS-TOTAL LIGNE / TOTAL T.C / T.C = line total
SOUS-TOTAL / TOTAL HT / TOTAL HTVA = subtotal before tax
TVA / CUMUL TVA / MONTANT TVA / MONTANT TAXE = tax amount
DROIT DE TIMBRE / TAXE TIMBRE = stamp duty — ADD to tax_amount
TOTAL TTC / NET A PAYER / PAIMENTS RECUS = total including tax (grand total)

=== TUNISIAN NUMBER FORMAT ===
Dots AND spaces are THOUSANDS separators. The 3 digits after the LAST separator = millimes.
  15.575.000 → 15575.000 TND   (NOT 15 million — fifteen thousand five hundred seventy-five dinars)
  22 176,003 → 22176.003 TND
  5.874.160  → 5874.160 TND
  1.000      → 1.000 TND
  1750       → 1.750 TND (unit prices in this range are per-unit in TND)
Output all amounts as TND float values (e.g. 15575.0, NOT 15575000).

=== TABLE READING: numbers before item name ===
Sometimes OCR reads numbers on a line BEFORE the item name (due to table layout).
Example: "PRIX UNITAIRE HRS/QTE SOUS-TOTAL\nARTICLE\n1750 8900 15.575.000\nPoussin chair"
→ item.designation="Poussin chair", item.unit_price=1.750, item.quantity=8900, item.line_total=15575.0
The column order is typically: [unit_price] [quantity] [line_total] before the description.

=== OUTPUT FORMAT ===
{
  "supplier_name": "company name from header/logo (NOT from CLIENT field)",
  "invoice_number": "invoice or delivery note number",
  "invoice_date": "YYYY-MM-DD or null",
  "items": [{"designation": "...", "quantity": number, "unit_price": number, "line_total": number}],
  "subtotal_htva": number,
  "tax_amount": number,
  "total_ttc": number,
  "currency": "TND"
}

=== AMOUNT IN WRITTEN-OUT WORDS (CRITICAL FALLBACK) ===
Many Tunisian invoices print the total in French words, introduced by:
"Arreté le présent bon à la somme de ...", "Arrêté à la somme de ...", etc.
When numeric table values are garbled/missing, extract total_ttc from these words.
OCR often garbles French words — map common substitutions:
  Ceni/Cent → 100 | Vingi/Vingt → 20 | Milles/Mille → 1000
  DN-HUII/Dix-Huit → 18 | 5DD/Cinq Cent → 500 (millimes)
  MIIPS/Millimes → fractional part separator
Examples of parsing:
  "Deux Milles Ceni Ouatre Vingi DN-HUII DinarS 5DD MIIPS"
   → 2×1000 + 100 + 4×20 + 18 = 2198 dinars + 500/1000 = 2198.500 TND → total_ttc = 2198.500
  "Cinq Mille Huit Cent Soixante Quatorze Dinars Cent Soixante Millimes"
   → 5874 dinars + 160/1000 = 5874.160 TND

=== DATE RULES ===
- The OCR preprocessing marks non-invoice dates as "[SKIP-DATE: label] date".
  NEVER use a date tagged [SKIP-DATE:...] as the invoice_date.
- ONLY use dates near labels "DATE", "DATE DE LA FACTURE", "Bon de Commande date".
- If no valid invoice date is found, output null for invoice_date.

Rules:
- Output null only if field truly not found. Never invent numbers.
- For unit_price: prefer P.U.H.T or Net Remise column over gross price before discount.
- Amounts that look like "1 445.000" or "1.445.000" mean 1445.000 TND (the space/dot is a thousands separator).
- Merge duplicate item lines with same description into one item. Ignore sub-descriptions (italic smaller text).
- Do not add items that are purely textual sub-descriptions with no numeric values.
"""

# JSON parsing helpers
INVOICE_FIELDS = {"supplier_name", "invoice_number", "invoice_date", "items", "subtotal_htva", "tax_amount", "total_ttc", "currency"}


_SKIP_DATE_LABELS = re.compile(
    r"(MAJ|Version|Modifi[eé]\s+le|Date\s+MAJ|DELAIS\s+DE\s+PAIMENT|DATE\s+ECHEANCE|"
    r"Bon\s+de\s+Sortie|Date\s+Sortie|Date\s+Livraison|Date\s+BL)\s*[:\-]?\s*",
    re.IGNORECASE,
)

# French number-words → integer value (handles common OCR garbling)
_FRENCH_NUM_WORDS: List[tuple] = [
    # garbled forms first, then canonical
    (r"(?:MIIPS?|Milli?mes?|MILLIME?S?)", ""),          # strip trailing Millimes label
    (r"D[NI][.\-]HUI[IT]|Dix[\-\s]?Huit",  "18"),
    (r"D[NI][.\-]NEU[FV]|Dix[\-\s]?Neuf",  "19"),
    (r"D[NI][.\-]SEPT|Dix[\-\s]?Sept",      "17"),
    (r"DIX[\-\s]?SIX|Seize",               "16"),
    (r"DIX[\-\s]?CINQ|Quinze",             "15"),
    (r"DIX[\-\s]?QUATRE|Quatorze",         "14"),
    (r"DIX[\-\s]?TROIS|Treize",            "13"),
    (r"DOUZE|DIX[\-\s]?DEUX",              "12"),
    (r"ONZE|DIX[\-\s]?UN",                 "11"),
    (r"DIX\b",                              "10"),
    (r"NEUF\b",                              "9"),
    (r"HUIT\b",                              "8"),
    (r"SEPT\b",                              "7"),
    (r"SIX\b",                               "6"),
    (r"CINQ\b",                              "5"),
    (r"QUATRE[\-\s]?VINGT[\-\s]?DIX\b",    "90"),
    (r"QUATRE[\-\s]?VINGT[S]?\b",           "80"),
    (r"SOIXANTE[\-\s]?DIX\b",               "70"),
    (r"SOIXANTE\b",                          "60"),
    (r"CINQUANTE\b",                         "50"),
    (r"QUARANTE\b",                          "40"),
    (r"TRENTE\b",                            "30"),
    (r"VINGI?\b",                            "20"),  # "Vingi" = garbled "Vingt"
    (r"VINGT[S]?\b",                         "20"),
    (r"QUATRE\b",                             "4"),
    (r"TROIS\b",                              "3"),
    (r"DEUX\b",                               "2"),
    (r"UNE?\b",                               "1"),
    (r"ZERO\b|ZÉRO\b",                        "0"),
    (r"MILLES?\b",                         "1000"),
    (r"CEN[TI]S?\b",                        "100"),  # "Ceni" = garbled "Cent"
]


def _parse_french_amount_words(phrase: str) -> Optional[float]:
    """
    Convert a French amount-in-words phrase (possibly OCR-garbled) to a float.
    Handles patterns like "Deux Milles Ceni Ouatre Vingi DN-HUII DinarS 5DD MIIPS"
    → 2198.500
    Returns None if the phrase cannot be parsed.
    """
    # Normalise
    s = phrase.upper().strip()

    # Split at DINARS to separate integer part (dinars) from fractional (millimes)
    dinar_split = re.split(r"DINARS?\b", s, maxsplit=1)
    dinar_part = dinar_split[0]
    milli_part = dinar_split[1] if len(dinar_split) > 1 else ""

    def _words_to_int(text: str) -> int:
        # Replace word tokens with numbers
        for pattern, replacement in _FRENCH_NUM_WORDS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        # Extract all numbers
        nums = [int(n) for n in re.findall(r"\d+", text)]
        if not nums:
            return 0
        # Simple left-to-right aggregation with multiplier logic
        result, current = 0, 0
        for n in nums:
            if n == 1000:
                result += (current or 1) * 1000
                current = 0
            elif n == 100:
                current = (current or 1) * 100
            else:
                current += n
        return result + current

    dinars = _words_to_int(dinar_part)
    if dinars <= 0:
        return None

    # Parse millimes: could be "Cinq Cent" = 500 or "5DD" = 500 or "000" = 0
    milli_part = re.sub(r"[^\w\s]", " ", milli_part)
    # Try digit extraction first (e.g. "5DD" → "5" + drop, "500")
    raw_milli_nums = re.findall(r"\d+", milli_part)
    if raw_milli_nums:
        milli_val = int(raw_milli_nums[0])
        # "500" → 0.500, "50" → 0.050, "5" → 0.005
        millimes = milli_val / 1000.0
    else:
        millimes = _words_to_int(milli_part) / 1000.0

    return round(dinars + millimes, 3)


def _extract_total_from_words(ocr_text: str) -> Optional[float]:
    """
    Find "Arreté le présent bon à la somme de …" or similar French patterns
    and extract the total amount from the written-out words.
    Returns None if not found or not parseable.
    """
    # Match "Arrete ... somme de [PHRASE] Dinars"
    m = re.search(
        r"(?i)arr[eêé]t[eée][^0-9\n]{0,80}?somme\s+de\s+([A-Za-zÀ-ÿ\s\-]+?Dinar[sS]?\s*[A-Za-z0-9\s\-]*?)(?:\n|La\s+Direction|Le\s+Client|Veh|$)",
        ocr_text,
        re.DOTALL,
    )
    if m:
        val = _parse_french_amount_words(m.group(1))
        if val and val > 0:
            return val
    return None


def _infer_year_from_invoice_number(inv_num: str) -> Optional[int]:
    """
    Infer invoice year from common invoice number formats:
      "FA005/2026"        → 2026
      "LIV-LJM-26-00119" → 2026
      "FAC-26004806"      → 2026
      "2025/005123"       → 2025
    """
    if not inv_num:
        return None
    # 4-digit year
    m = re.search(r"\b(20\d{2})\b", inv_num)
    if m:
        return int(m.group(1))
    # 2-digit year between separators: "-26-" or at start with digits: "FAC-26XXXXX"
    m = re.search(r"(?:^|[-/_])(\d{2})(?:[-/_]|\d{4,})", inv_num)
    if m:
        yy = int(m.group(1))
        if 20 <= yy <= 50:
            return 2000 + yy
    return None


def _preprocess_ocr_for_llm(text: str) -> str:
    """
    Pre-process OCR text before sending to LLM:
    1. Annotate MAJ/Version dates so LLM skips them.
    2. Convert Tunisian number format (1.445.000 → 1445.000).
    """
    # 1. Mark non-invoice dates so LLM knows to skip them
    text = _SKIP_DATE_LABELS.sub(r"[SKIP-DATE: \g<1>] ", text)

    def replace_dot_thousands(m: re.Match) -> str:
        raw = m.group(0)
        parts = raw.split(".")
        if len(parts) >= 3 and all(len(p) == 3 for p in parts[1:]):
            return "".join(parts[:-1]) + "." + parts[-1]
        return raw

    def replace_space_comma_thousands(m: re.Match) -> str:
        return m.group(0).replace(" ", "").replace(",", ".")

    # 2a. 15.575.000 or 1.445.000
    text = re.sub(r"\d{1,3}(?:\.\d{3}){2,}", replace_dot_thousands, text)
    # 2b. 22 176,003 (space-thousands + comma-decimal)
    text = re.sub(r"\d{1,3}(?:\s\d{3})+[,]\d{3}", replace_space_comma_thousands, text)
    # 2c. 1 445.000 (single-space thousands + dot-decimal)
    text = re.sub(r"\b(\d{1,3})\s(\d{3})\.(\d{3})\b", r"\1\2.\3", text)

    return text


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


def _eval_json_arithmetic(raw: str) -> str:
    """
    Replace simple arithmetic expressions inside JSON numeric values before parsing.
    e.g. '"tax_amount": 17.795 + 1.0' → '"tax_amount": 18.795'
    """
    import re as _re

    def replacer(m: re.Match) -> str:
        expr = m.group(1).strip()
        try:
            result = eval(expr, {"__builtins__": {}})  # noqa: S307 — safe: only numbers
            return f": {round(float(result), 6)}"
        except Exception:
            return m.group(0)

    # Match patterns like: ': 17.795 + 1.0' or ': 100 * 5.5' etc.
    return _re.sub(r":\s*([\d.]+\s*[\+\-\*\/]\s*[\d.]+)", replacer, raw)


def _parse_json_from_response(raw: str) -> Dict:
    """Parse and normalize the first JSON object found in an LLM response."""
    raw = raw.strip()
    # Pre-evaluate any arithmetic expressions the LLM may have placed in values
    raw = _eval_json_arithmetic(raw)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"No valid JSON in LLM response: {raw[:300]!r}")
        obj = json.loads(match.group())

    return _unwrap_llm_obj(obj)


def _apply_invoice_defaults(obj: Dict, ocr_text: str = "") -> Dict:
    """Normalize and post-process extracted invoice data."""
    # String fields — convert None to empty string
    for f in ("supplier_name", "invoice_number", "invoice_date"):
        v = obj.get(f)
        obj[f] = str(v).strip() if v is not None else ""

    # ── Date validation against invoice number year ───────────────────────────
    # e.g. "LIV-LJM-26-00119" → year 2026; if LLM extracted 2024 → clear it
    inv_year = _infer_year_from_invoice_number(obj["invoice_number"])
    if inv_year and obj["invoice_date"]:
        try:
            date_year = int(obj["invoice_date"][:4])
            if date_year != inv_year and abs(date_year - inv_year) > 1:
                logger.info(
                    "invoice_date year %d ≠ invoice_number year %d → clearing date",
                    date_year, inv_year,
                )
                obj["invoice_date"] = ""
        except (ValueError, TypeError):
            pass

    # Currency
    if not obj.get("currency"):
        obj["currency"] = "TND"

    # Numeric fields — convert None to 0.0
    for f in ("subtotal_htva", "tax_amount", "total_ttc"):
        v = obj.get(f)
        try:
            obj[f] = float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            obj[f] = 0.0

    # Ensure items is a list
    if not isinstance(obj.get("items"), list):
        obj["items"] = []

    # Process and clean each item
    cleaned_items = []
    for item in obj["items"]:
        if not isinstance(item, dict):
            continue
        item["designation"] = str(item.get("designation") or "").strip()
        for f in ("quantity", "unit_price", "line_total"):
            v = item.get(f)
            try:
                item[f] = float(v) if v is not None else 0.0
            except (TypeError, ValueError):
                item[f] = 0.0

        # Bidirectional reconciliation: compute missing field from the other two
        qty, pu, lt = item["quantity"], item["unit_price"], item["line_total"]
        if qty > 0 and pu > 0 and lt == 0:
            item["line_total"] = round(qty * pu, 3)
        elif qty > 0 and lt > 0 and pu == 0:
            item["unit_price"] = round(lt / qty, 3)
        elif pu > 0 and lt > 0 and qty == 0:
            item["quantity"] = round(lt / pu, 3)

        # Skip items where ALL numeric fields are 0 (phantom/duplicate items)
        if item["quantity"] == 0 and item["unit_price"] == 0 and item["line_total"] == 0:
            continue
        cleaned_items.append(item)
    obj["items"] = cleaned_items

    # ── Scale factor correction ───────────────────────────────────────────────
    # Tunisian invoices show amounts in TND with 3 decimal (millimes).
    # If total_ttc > 100,000 it was returned in raw millimes — divide by 1000.
    total = obj.get("total_ttc", 0.0)
    if total and total > 100_000:
        factor = 1000.0
        obj["total_ttc"]     = round(total                      / factor, 3)
        obj["subtotal_htva"] = round(obj.get("subtotal_htva", 0) / factor, 3)
        obj["tax_amount"]    = round(obj.get("tax_amount", 0)    / factor, 3)
        for item in obj["items"]:
            if item.get("unit_price", 0) > 500:          # > 500 TND/unit → likely in millimes
                item["unit_price"] = round(item["unit_price"] / factor, 3)
            if item.get("line_total", 0) > 10_000:       # > 10,000 → scale down
                item["line_total"] = round(item["line_total"] / factor, 3)
        # Re-run bidirectional reconciliation after scale correction
        for item in obj["items"]:
            qty, pu, lt = item["quantity"], item["unit_price"], item["line_total"]
            if qty > 0 and pu > 0 and abs(lt - round(qty * pu, 3)) > 1:
                item["line_total"] = round(qty * pu, 3)

    # ── Item sanity: drop items with line_total > invoice total (clearly wrong) ─
    total_ttc = obj.get("total_ttc", 0.0)
    if total_ttc > 0:
        obj["items"] = [
            i for i in obj["items"]
            if i.get("line_total", 0) <= total_ttc * 1.15 or i.get("line_total", 0) == 0
        ]

    # ── Derived totals ────────────────────────────────────────────────────────
    # If subtotal is 0 but items exist, compute from items
    if obj["items"] and obj["subtotal_htva"] == 0:
        obj["subtotal_htva"] = round(sum(i.get("line_total", 0) for i in obj["items"]), 3)

    # If total_ttc is 0 but subtotal + tax > 0, compute
    if obj["total_ttc"] == 0 and (obj["subtotal_htva"] > 0 or obj["tax_amount"] > 0):
        obj["total_ttc"] = round(obj["subtotal_htva"] + obj["tax_amount"], 3)

    # ── Amount-in-words fallback (for ACIT-like invoices with garbled tables) ─
    # When total_ttc is 0 or suspiciously high vs. items, try to extract from
    # the French "Arreté le présent bon à la somme de …" section.
    if ocr_text:
        words_total = _extract_total_from_words(ocr_text)
        if words_total:
            current_total = obj.get("total_ttc", 0.0)
            # Use words-total if: (a) current total is 0, or
            # (b) current total is >20% higher and items are empty (likely HT total)
            if current_total == 0:
                obj["total_ttc"] = words_total
                logger.info("total_ttc set from amount-in-words: %.3f", words_total)
            elif (
                not obj["items"]
                and current_total > words_total * 1.10
                and words_total > 100
            ):
                logger.info(
                    "total_ttc replaced by amount-in-words %.3f (was %.3f, no items)",
                    words_total, current_total,
                )
                obj["total_ttc"] = words_total

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
        obj = _apply_invoice_defaults(_parse_json_from_response(raw), ocr_text=ocr_text)
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
        obj = _apply_invoice_defaults(json.loads(content), ocr_text=ocr_text)
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
    
    obj = _apply_invoice_defaults(_unwrap_llm_obj(data), ocr_text=ocr_text)
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
    
    preprocessed = _preprocess_ocr_for_llm(ocr_text)
    user_content = f"TRANSACTION TYPE: {transaction_type}\nOCR TEXT:\n{preprocessed}"

    def _parse_groq_response(raw_content: str) -> Dict:
        """Parse and apply defaults to a Groq JSON response string."""
        fixed = _eval_json_arithmetic(raw_content)
        obj = _parse_json_from_response(fixed)
        return _apply_invoice_defaults(obj, ocr_text=ocr_text)

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": INVOICE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            model=model,
            response_format={"type": "json_object"},
        )
        content = chat_completion.choices[0].message.content
        if not content:
            raise RuntimeError("Groq returned empty content")
        return _parse_groq_response(content)

    except Exception as e:
        # Groq may return HTTP 400 (json_validate_failed) when LLM generates
        # arithmetic expressions like "17.795 + 1.0" in JSON values.
        # Recover by extracting the failed_generation from the error body.
        failed_gen: str | None = None
        try:
            body = getattr(e, "body", None) or {}
            failed_gen = body.get("error", {}).get("failed_generation")
        except Exception:
            pass

        if failed_gen:
            try:
                logger.info("Groq json_validate_failed — recovering from failed_generation")
                return _parse_groq_response(failed_gen)
            except Exception as inner_e:
                logger.warning("Recovery from failed_generation failed: %s", inner_e)

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


async def extract_invoice_from_ocr(
    ocr_text: str, transaction_type: str
) -> tuple:
    """
    Wrapper used by invoice_processing.py.
    Returns (extracted_dict, confidence_float).
    """
    extracted = await extract_invoice_fields(ocr_text, transaction_type)
    # Compute a simple confidence score: ratio of non-empty key fields
    key_fields = [
        extracted.get("supplier_name"),
        extracted.get("invoice_number"),
        extracted.get("invoice_date"),
        extracted.get("total_ttc"),
    ]
    filled = sum(1 for v in key_fields if v)
    confidence = round(filled / len(key_fields), 2)
    if extracted.get("items"):
        confidence = min(1.0, confidence + 0.1)
    return extracted, confidence
