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

Common Tunisian/French terms: FACTURE=invoice, BON DE LIVRAISON=delivery note,
FOURNISSEUR=supplier, CLIENT=customer, DESIGNATION=product description,
QUANTITÉ=quantity, PRIX UNITAIRE=unit price, TOTAL LIGNE=line total,
SOUS-TOTAL=subtotal (HTVA), TVA=tax, TOTAL TTC=total with tax,
DEN=دينار (TND), EUROS=euros (EUR), DOLLARS=dollars (USD)
Amount format: dots group thousands, comma is decimals/millimes (e.g. 15.576,000 TND = 15576.000 TND).
May appear as 15.576.000 (two dot patterns) — treat as 15576.000 in TND context.

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

# --- Heuristic extraction from raw OCR (FR / TN invoices when LLM fails) ---

_SUPPLIER_LINE_RE = re.compile(
    r"(?im)^\s*(STE|SARL|EURL|ETS|S\.?\s*A\.?\s*R\.?\s*L\.?)\s+(.{3,120})\s*$"
)
_DATE_DM_RE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b")
_INV_NUM_RE = re.compile(
    r"(?i)(?:n[o°]\s*facture|facture\s*n[o°]|facture|n[o°]|n\.|réf|ref)\s*[:\s]?\s*([A-Z0-9][A-Z0-9\-/]{4,30})"
)
_INV_FA_REF_RE = re.compile(r"\b(FA\d{2,8}/\d{4})\b", re.I)
_INV_BL_REF_RE = re.compile(r"\b([A-Z]{1,4}[\-]?\d{2,10}/\d{4})\b", re.I)
_CLIENT_MF_RE = re.compile(
    r"(?i)\b(\d{5,12}(?:/[A-Z0-9]+)+(?:/\d{3})?)\b",
)
# Long OCR-glued rows (detail + "Product qty pu total") need >45 chars before first number.
_LINE_ITEM_RE = re.compile(
    r"(?im)^\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9\s%'\-]{2,180}?)\s+"
    r"(\d(?:[\d\s.,]{0,14}))\s+(\d(?:[\d\s.,]{0,14}))\s+(\d(?:[\d\s.,]{0,16}))\s*$"
)


def _parse_amount_token(raw: str) -> float | None:
    """Parse FR/TN amounts: 15.575,000, 15 575,000, 22 176,003, 15,575.000."""
    if not raw or not str(raw).strip():
        return None
    t = str(raw).strip().replace("\u00a0", " ")
    t = re.sub(r"(?i)TND|EUR|USD|DT|DNT|QX\b", "", t).strip()
    if not t or not any(c.isdigit() for c in t):
        return None
    # "44 723.000" / "8 407.070" — espaces milliers, dernier bloc .### = millimes TN
    m_spdot = re.fullmatch(r"(\d{1,3}(?:\s\d{3})+)\.(\d{3,4})$", t)
    if m_spdot:
        whole = m_spdot.group(1).replace(" ", "")
        frac = m_spdot.group(2)
        try:
            return float(f"{whole}.{frac}")
        except ValueError:
            pass
    # "5 810,000" / "22 176,003" — spaces = thousands, comma = decimal (millimes)
    m_sp = re.fullmatch(r"(\d{1,3}(?:\s\d{3})*)([.,])(\d{1,4})", t)
    if m_sp:
        segs = m_sp.group(1).split()
        if not (len(segs) == 2 and all(len(x) == 3 for x in segs)):
            whole = m_sp.group(1).replace(" ", "")
            frac = m_sp.group(3)
            try:
                return float(f"{whole}.{frac}")
            except ValueError:
                pass
    # Qty + PU on one line: "100 116,200" (two 3-digit groups before comma) — not one amount
    if re.fullmatch(r"\d{3}\s\d{3},\d+", t):
        return None
    s = re.sub(r"\s+", "", t)
    if not any(c.isdigit() for c in s):
        return None
    # 15.575,000 — dots thousands, comma decimals
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+,\d+", s):
        return float(s.replace(".", "").replace(",", "."))
    # 15,575.000
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+\.\d+", s):
        return float(s.replace(",", ""))
    # 15.576.000 — last .### is millimes (TN), not another thousand group
    m_tri = re.fullmatch(r"(\d{1,3}(?:\.\d{3})+)\.(\d{1,4})$", s)
    if m_tri:
        return float(m_tri.group(1).replace(".", "") + "." + m_tri.group(2))
    # Only thousands with dots, no trailing fraction: rare compact form
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
        return float(s.replace(".", ""))
    # Simple decimal comma (no thousand groups)
    if s.count(",") == 1 and s.count(".") == 0:
        try:
            return float(s.replace(",", "."))
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


_AMT_TOKEN_RE = re.compile(
    r"\d{1,3}(?:\s\d{3})+,\d+|\d{1,3}(?:\s\d{3})+\.\d+|\d{1,3}(?:\.\d{3})+,\d+|\d{1,3}(?:\.\d{3})+\.\d+"
    r"|\d+,\d{2,4}(?!\d)|\d[\d\s.,]{0,22}\d|\d{2,}"
)


def _amounts_from_spaced_tail(tail: str) -> list[float]:
    """
    Parse space-separated amount tokens (50,00 100 116,200 5 810,000).
    Prefer the longest valid chunk from each index so "5 810,000" and "1 464,000" merge,
    but avoid eating "50,00 100" as one number.
    """
    parts = [p for p in re.split(r"\s+", tail.strip()) if p]
    vals: list[float] = []
    i = 0
    n = len(parts)
    while i < n:
        best: tuple[int, float] | None = None
        max_w = min(4, n - i)
        for w in range(max_w, 0, -1):
            chunk = " ".join(parts[i : i + w])
            v = _parse_amount_token(chunk)
            if v is None or _is_likely_year(v):
                continue
            if w >= 2 and re.search(r",\d{1,4}\s+\d", chunk):
                continue
            best = (i + w, float(v))
            break
        if best:
            vals.append(best[1])
            i = best[0]
        else:
            i += 1
    return vals


def _extract_numbers_from_line(line: str) -> list[float]:
    """Find numeric tokens in a line (incl. '5 810,000')."""
    out: list[float] = []
    for m in _AMT_TOKEN_RE.finditer(line):
        v = _parse_amount_token(m.group(0))
        if v is not None and not _is_likely_year(v):
            out.append(v)
    return out


def _space_separated_amount_tally(line: str) -> int:
    """Count whitespace-separated tokens that parse as amounts (not years)."""
    n = 0
    for p in re.split(r"\s+", line.strip()):
        if not p or not any(ch.isdigit() for ch in p):
            continue
        v = _parse_amount_token(p)
        if v is not None and not _is_likely_year(v):
            n += 1
    return n


# Table row like "613 ALCO 7 PRIMO …" — must not be glued onto client/city line above.
_STPA_SKU_LINE_START = re.compile(r"^\s*\d{3}\s+[A-Za-zÀ-ÿ]")


def _is_probable_table_header_line(cur: str) -> bool:
    """Évite de coller la ligne d’en-tête colonnes sur la première ligne article."""
    ul = (cur or "").strip().upper()
    if len(ul) > 160:
        return False
    keys = (
        "DESIGNATION",
        "ARTICLE",
        "LIBELLE",
        "UNITE",
        "QTE",
        "QUANTIT",
        "P.U",
        "PU ",
        "P.HT",
        "P HT",
        "MONTANT",
        "SOUS-TOTAL",
    )
    hits = sum(1 for k in keys if k in ul)
    return hits >= 2


def _glue_skip_client_or_table_boundary(cur: str, nxt: str) -> bool:
    """Avoid merging client name / locality with the first numeric product row (STPA, SOCEP city)."""
    if not cur or not nxt or any(ch.isdigit() for ch in cur):
        return False
    if _STPA_SKU_LINE_START.match(nxt):
        return True
    if re.match(r"(?i)^(STE|SARL|EURL|ETS)\b", cur.strip()):
        return True
    parts = cur.split()
    if (
        1 <= len(parts) <= 4
        and cur.strip().upper() == cur.strip()
        and len(cur.strip()) <= 48
        and re.fullmatch(r"[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s'\-]+", cur.strip().upper())
    ):
        return True
    return False


def _glue_split_numeric_followups(text: str) -> str:
    """
    OCR often puts the product label on one line and qty / PU / total on the next.
    Glue those pairs so line-item regexes can fire.
    """
    raw = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(raw):
        line = raw[i]
        cur = line.strip()
        nxt = raw[i + 1].strip() if i + 1 < len(raw) else ""
        if cur and nxt and len(cur) >= 4:
            nums_cur = _extract_numbers_from_line(cur)
            if len(nums_cur) < 2:
                nums_cur = _space_separated_amount_tally(cur)
            else:
                nums_cur = len(nums_cur)
            n_tally = _space_separated_amount_tally(nxt)
            has_label = bool(re.search(r"[A-Za-zÀ-ÿ]{4,}", cur))
            if (
                has_label
                and nums_cur < 2
                and n_tally >= 3
                and not _is_probable_table_header_line(cur)
                and not _glue_skip_client_or_table_boundary(cur, nxt)
                and not re.match(
                    r"(?i)^(total|sous|tva|timbre|net|facture|date|n°|n[o°]|réf|ref|client|societe|mf|matricule)\b",
                    cur,
                )
            ):
                out.append(f"{cur.rstrip()} {nxt.strip()}")
                i += 2
                continue
        out.append(line)
        i += 1
    return "\n".join(out)


def _is_likely_year(n: float) -> bool:
    return 1990 <= n <= 2100 and abs(n - int(n)) < 0.001


_ISSUER_LINE_HINT = re.compile(
    r"(?i)\b(SOCEP\b|S\.?O\.?C\.?E\.?P\b|STE\s+DE\s+CENTRE\s+DES\s+POUSSINS|"
    r"MEDIMIX|alfa\s+NUTRITION|TAGHDHIA|TAHAR\s+TLILI|\bACT\s+T\b|"
    r"USINE\s+D['\u2019]?\s*ALIMENTS|SOCIETE\s+TUNISIENNE|"
    r"S\.?T\.?P\.?A\.|ALIMENTS\s+COMPOSES\s+DU\s+NORD|\bACN\b|"
    r"LES\s+ALIMENTS\s+COMPOSES)\b"
)


def _heur_find_issuer_line(text: str) -> str:
    """Vendor / issuer line (top of invoice)."""
    best = ""
    for ln in text.splitlines()[:55]:
        s = ln.strip()
        if not s or len(s) < 3:
            continue
        if "SOCEP" in s.upper() or _ISSUER_LINE_HINT.search(s):
            if len(s) > len(best):
                best = s
    return best[:240]


def _heur_client_line_from_block(lines: list[str], start_i: int, max_ahead: int = 10) -> str:
    """Première ligne plausible (raison sociale) après un libellé."""
    n = len(lines)
    for j in range(start_i + 1, min(start_i + max_ahead, n)):
        line = lines[j].strip()
        if len(line) < 3:
            continue
        ul = line.upper()
        if re.match(r"^(M\.?\s*F\.?|MF|MATRICULE|ADRESSE|TEL|FAX|N°|DATE)\b", ul):
            continue
        if re.match(r"^\d+$", line) or re.match(r"^[A-Z]?\d{1,2}[/:.-]\d", line):
            continue
        if re.search(r"[A-Za-zÀ-ÿ]", line):
            return line[:240]
    return ""


def _heur_find_client_line(text: str) -> str:
    """Destinataire : bloc après SOCIETE (ligne suivante) ou CLIENT / DESTINATAIRE."""
    raw_lines = (text or "").splitlines()
    lines = [ln.rstrip() for ln in raw_lines]

    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        ul = s.upper()
        if re.match(r"^SOCIETE\s*:?\s*$", ul):
            got = _heur_client_line_from_block(lines, i)
            if got:
                return got
        if ul.startswith("SOCIETE") and ":" in s:
            rest = s.split(":", 1)[1].strip()
            if len(rest) >= 4 and re.search(r"[A-Za-zÀ-ÿ]", rest):
                return rest[:240]
            got = _heur_client_line_from_block(lines, i)
            if got:
                return got

    ul_full = text.upper()
    for marker in ("CLIENT", "CUSTOMER", "CLIENTE", "DESTINATAIRE"):
        idx = ul_full.find(marker)
        if idx < 0:
            continue
        snippet = text[idx : idx + 600]
        for line in snippet.splitlines()[1:10]:
            line = line.strip()
            if len(line) < 4:
                continue
            if re.match(r"^\d+$", line) or re.match(r"^[A-Z]?\d+[/:]\d+", line):
                continue
            if re.search(r"[A-Za-zÀ-ÿ]", line):
                return line[:240]
    return ""


def _sanitize_supplier_name(name: str) -> str:
    """Strip trailing OCR/LLM garbage after a plausible company name (e.g. 'Puis ins Bip')."""
    name = re.sub(r"\s+", " ", (name or "").strip())
    if len(name) < 4:
        return name
    cut = re.search(
        r"(?i)\s+(puis|donc|alors|page|ref|voir|ins|bip|photo|image|cid|c_|http)\s+",
        name,
    )
    if cut and cut.start() > 14:
        name = name[: cut.start()].strip()
    m = re.match(
        r"(?is)^((?:STE|SARL|EURL|ETS|SOCIETE|USINE)\s+.{8,200}?)(?:\s+\d{8,})?$",
        name,
    )
    if m:
        cand = re.sub(r"\s+", " ", m.group(1).strip())
        if len(cand) >= 12:
            name = cand[:240]
    return name[:240]


def _heur_abbes_header_fallback(text: str) -> str:
    """Issuer is STE ABBES (own invoices) — layout has ABBES in header, not only under CLIENT."""
    lines = text.splitlines()[:20]
    block = "\n".join(lines)
    if not re.search(r"(?i)STE\s+ABBES|ABBES\s+POUR\s+VOLAILLE", block):
        return ""
    for ln in lines:
        s = ln.strip()
        if len(s) < 12:
            continue
        if re.search(r"(?i)ABBES", s) and re.search(r"(?i)\bSTE\b|SARL\b", s):
            return s[:240]
    return ""


def _heur_find_supplier_legacy(text: str) -> str:
    m = _SUPPLIER_LINE_RE.search(text)
    if m:
        return f"{m.group(1).strip()} {m.group(2).strip()}".strip()[:240]
    for marker in ("FOURNISSEUR", "FOURNISSEURE", "VENDEUR"):
        idx = text.upper().find(marker)
        if idx >= 0:
            snippet = text[idx : idx + 400]
            for line in snippet.splitlines()[1:4]:
                line = line.strip()
                if len(line) > 4 and not line[:1].isdigit():
                    return line[:240]
    return ""


def _heur_top_non_abbes_company(text: str) -> str:
    """First header line that looks like a supplier and is not STE ABBES (bill-to)."""
    for ln in text.splitlines()[:35]:
        s = ln.strip()
        if len(s) < 8 or "ABBES" in s.upper():
            continue
        if _ISSUER_LINE_HINT.search(s):
            return s[:240]
        if re.search(r"(?i)^(STE|SARL|EURL|SOCIETE|USINE)\s+", s):
            return s[:240]
    return ""


def _heur_emitter_before_client_block(text: str) -> str:
    """Raison sociale au-dessus du bloc CLIENT / SOCIETE (devis, factures tierces)."""
    lines = (text or "").splitlines()
    stop = len(lines)
    for i, ln in enumerate(lines):
        ul = ln.strip().upper()
        if re.match(r"^(CLIENT|SOCIETE\s*:|DESTINATAIRE|ACHETEUR)\s*$", ul):
            stop = i
            break
    for ln in lines[:stop]:
        s = ln.strip()
        if len(s) < 6:
            continue
        if re.search(r"(?i)^(MF|M\.F|TEL|FAX|DATE|N°|DEVIS|FACTURE|SOUS-TOTAL|TOTAL)\b", s):
            continue
        if s.upper() in ("EAE",):
            continue
        if re.search(
            r"(?i)\b(STE|SARL|EURL|ETS|SOCIETE|SOCIÉTÉ|ENTREPRISE|USINE|EURL)\b",
            s,
        ):
            return s[:240]
    return ""


def _heur_find_supplier(text: str, transaction_type: str) -> str:
    """
    buy: issuer (vendor), not bill-to client when distinguishable.
    sell: prefer client / buyer on the invoice.
    """
    tx = (transaction_type or "buy").lower()
    if tx == "sell":
        client = _heur_find_client_line(text)
        if client:
            return client
        return _heur_find_supplier_legacy(text)

    issuer = _heur_find_issuer_line(text)
    if issuer:
        return issuer
    abbes_hdr = _heur_abbes_header_fallback(text)
    if abbes_hdr:
        return abbes_hdr
    client = (_heur_find_client_line(text) or "").strip()
    leg = _heur_find_supplier_legacy(text).strip()
    lu, cu = (leg.upper(), client.upper()) if leg else ("", "")

    if leg and client and lu == cu:
        return leg[:240]
    if leg and client and "ABBES" in lu and "ABBES" in cu:
        alt = _heur_top_non_abbes_company(text)
        if alt:
            return alt
    if leg and client and lu not in cu and cu not in lu:
        return leg[:240]
    if leg:
        return leg[:240]
    emit = _heur_emitter_before_client_block(text)
    if emit and client and emit.strip().upper() != client.strip().upper():
        return emit[:240]
    return client or ""


def _fix_line_designation_ocr(desig: str, ctx_upper: str) -> str:
    """Corrections Courantes OCR sur libellés produits (contexte volaille / TN)."""
    d = re.sub(r"\s+", " ", (desig or "").strip())
    if not d:
        return d
    food = bool(
        re.search(
            r"(?i)POUSSIN|CHAIR|VOLAILLE|ALIMENT|SOCEP|ABBES|POUSSINS|CENTRE\s+DES\s+POUSSINS",
            ctx_upper,
        )
    )
    if food:
        if re.match(r"(?i)^ate\s+", d):
            d = re.sub(r"(?i)^ate\s+", "Poussin ", d, count=1)
        elif d.strip().lower() in ("ate", "ate."):
            d = "Poussin chair"
        if re.search(r"(?i)poussin\s+cha1r|poussin\s+chail", d):
            d = re.sub(r"(?i)cha1r|chail", "chair", d)
    return d[:200]


def _heur_invoice_number_line_first(text: str) -> str:
    """Priorité : même ligne que N° FACTURE / FACTURE N°, puis référence FA… / BL…."""
    for ln in (text or "").splitlines():
        ls = ln.strip()
        if len(ls) < 5:
            continue
        ul = ls.upper()
        if re.search(r"(?i)N[°O\.\s]*FACTURE|FACTURE\s*N[°O]", ul):
            m = _INV_FA_REF_RE.search(ls)
            if m:
                return m.group(1).strip()[:80]
            m2 = _INV_BL_REF_RE.search(ls)
            if m2 and len(m2.group(1)) <= 36:
                return m2.group(1).strip()[:80]
            m3 = re.search(
                r"(?i)(?:N[°O\.\s]*FACTURE|FACTURE\s*N[°O])\s*[:\s]*([A-Z0-9][A-Z0-9\-/]{3,34})",
                ls,
            )
            if m3 and not re.match(r"^20\d{2}$", m3.group(1)):
                return m3.group(1).strip()[:80]
    return ""


def _heur_find_invoice_number(text: str) -> str:
    for ln in (text or "").splitlines():
        ls = ln.strip()
        ul = ls.upper()
        if re.search(r"(?i)\bDEVIS\s*N", ul):
            m = re.search(
                r"(?i)DEVIS\s*N[°O.\s]*[:\s]*([A-Z0-9][A-Z0-9\-/]{2,42})",
                ls,
            )
            if m:
                cand = m.group(1).strip()
                if not re.fullmatch(r"\d{1,2}", cand):
                    return cand[:80]
    hit = _heur_invoice_number_line_first(text)
    if hit:
        return hit
    m = _INV_FA_REF_RE.search(text)
    if m:
        return m.group(1).strip()[:80]
    m = _INV_NUM_RE.search(text)
    if m:
        return m.group(1).strip()[:80]
    return ""


def _heur_find_payment_due_date(text: str) -> str:
    """Date d’échéance après DELAIS DE PAIEMENT, ÉCHÉANCE, etc."""
    for ln in (text or "").splitlines():
        ul = ln.upper()
        if not re.search(
            r"(?i)DELAI|DÉLAI|ECHEANCE|ÉCHÉANCE|PAIEMENT\s*AVANT|DATE\s+LIMITE",
            ul,
        ):
            continue
        m = _DATE_DM_RE.search(ln)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                return f"{y:04d}-{mo:02d}-{d:02d}"
    return ""


def _heur_find_client_tax_id(text: str, client_name: str = "") -> str:
    raw = text or ""
    lines = raw.splitlines()
    start_i = 0
    for i, ln0 in enumerate(lines):
        ul0 = ln0.strip().upper()
        if re.match(
            r"^(CLIENT|SOCIETE\s*:?\s*|DESTINATAIRE|ACHETEUR|FACTURER?\s*A)\s*$",
            ul0,
        ):
            start_i = i + 1
            break
    segment_lines = lines[start_i:] if start_i else lines
    for ln in segment_lines:
        ls = ln.strip()
        m = _CLIENT_MF_RE.search(ls)
        if m:
            return m.group(1).strip()[:80]
        if re.search(r"(?i)\bM\.?\s*F\.?\s*[\.:]?\s*", ls):
            rest = re.split(r"(?i)\bM\.?\s*F\.?\s*[\.:]?\s*", ls, maxsplit=1)
            if len(rest) > 1 and rest[1].strip():
                cand = rest[1].strip().split()[0][:80]
                if len(cand) >= 5:
                    return cand
    if client_name:
        ul_full = "\n".join(segment_lines).upper()
        idx = ul_full.find((client_name or "").strip().upper()[:20])
        if idx >= 0:
            snippet = "\n".join(segment_lines)[idx : idx + 800]
            m2 = _CLIENT_MF_RE.search(snippet)
            if m2:
                return m2.group(1).strip()[:80]
    return ""


def _heur_find_client_city(text: str, client_name: str) -> str:
    if not client_name or not (client_name or "").strip():
        return ""
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    cn = (client_name or "").strip().upper()
    for i, ln in enumerate(lines):
        if cn in ln.upper():
            for j in range(i + 1, min(i + 12, len(lines))):
                cand = lines[j].strip()
                if len(cand) < 3 or len(cand) > 80:
                    continue
                cul = cand.upper()
                if _CLIENT_MF_RE.search(cand):
                    continue
                if re.match(
                    r"(?i)^(MF|M\.F|MATRICULE|N°|DATE|SOCIETE|CLIENT|FACTURE|TEL|FAX)\b",
                    cul,
                ):
                    continue
                if re.search(
                    r"(?i)^(DESIGNATION|ARTICLE|LIBELLE|UNITE|QTE|QUANT|P\.U|P\.HT)\b",
                    cul,
                ):
                    continue
                if re.search(r"^\d+[\s.,]+\d+[\s.,]+\d", cand):
                    continue
                if _STPA_SKU_LINE_START.match(cand):
                    continue
                if _space_separated_amount_tally(cand) >= 3:
                    continue
                if any(ch.isdigit() for ch in cand):
                    continue
                if re.search(r"[A-Za-zÀ-ÿ]{3,}", cand) and not re.match(r"^\d+$", cand):
                    return cand[:120]
            break
    return ""


def _heur_supplier_split(issuer_line: str) -> tuple[str, str]:
    """SOCEP → nom court + raison sociale ; sinon conserver la ligne complète (évite « STE » seul)."""
    line = re.sub(r"\s+", " ", (issuer_line or "").strip())
    if not line:
        return "", ""
    if re.match(r"(?i)^SOCEP\b", line):
        return "SOCEP", line[:240]
    return line[:240], line[:240]


_PHONE_TN_LINE_RE = re.compile(
    r"(?i)(?:TEL|FIX|TÉL|TÉLEPHONE|MOBILE|GSM)[.:\s]*(\d{2}[\s.-]?\d{3}[\s.-]?\d{3})\b"
)
_PHONE_DOT_RE = re.compile(r"\b(\d{2}\.\d{3}\.\d{3})\b")
_SUP_TAX_COMPACT_RE = re.compile(r"\b(\d{6,9}[A-Z])\b", re.I)


def _heur_document_type_from_text(text: str) -> str:
    ul = (text or "").upper()
    if re.search(
        r"\b(DEVIS|PROPOSITION\s+COMMERCIALE|OFFRE\s+COMMERCIALE)\b",
        ul,
    ):
        return "quote"
    if re.search(r"\bQUOTE\b", text or "", re.I):
        return "quote"
    return "invoice"


def _heur_supplier_phone(text: str) -> str:
    raw = (text or "")[:4500]
    m = _PHONE_TN_LINE_RE.search(raw)
    if not m:
        m = _PHONE_DOT_RE.search(raw)
    if not m:
        return ""
    g = m.group(1)
    return re.sub(r"[\s-]+", ".", g.strip())[:32]


def _heur_supplier_tax_id_top(text: str) -> str:
    lines = (text or "").splitlines()[:48]
    in_client = False
    for ln in lines:
        ul = ln.upper()
        if re.search(r"\b(CLIENT|SOCIETE\s*:|DESTINATAIRE|ACHETEUR)\b", ul):
            in_client = True
        if _CLIENT_MF_RE.search(ln) and (in_client or "/" in ln):
            continue
        m = _SUP_TAX_COMPACT_RE.search(ln)
        if m and "/" not in ln.strip():
            return m.group(1).upper()[:32]
    return ""


def _heur_supplier_city_after_phone(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines()[:38]]
    for i, s in enumerate(lines):
        if re.search(r"(?i)TEL|FIX|TÉL|GSM", s) and i + 1 < len(lines):
            nxt = lines[i + 1]
            if (
                nxt
                and 2 <= len(nxt.split()) <= 6
                and not any(ch.isdigit() for ch in nxt)
                and not re.match(
                    r"(?i)^(MF|M\.F|N°|DATE|DEVIS|FACTURE|TOTAL|SOUS)\b",
                    nxt,
                )
            ):
                return nxt[:120]
    return ""


def _heur_tax_rate_percent(text: str) -> float | None:
    m = re.search(r"(?i)TVA\s*[:\s]*(\d{1,2}(?:[.,]\d+)?)\s*%", text or "")
    if not m:
        m = re.search(r"(?i)(\d{1,2})\s*%\s*(?:TVA|T\.V\.A\b)", text or "")
    if not m:
        return None
    v = m.group(1).replace(",", ".")
    try:
        x = float(v)
        return x if 0 < x < 35 else None
    except ValueError:
        return None


def _heur_find_paid_and_remaining(text: str) -> tuple[float | None, float | None]:
    paid: float | None = None
    remaining: float | None = None
    for ln in (text or "").splitlines():
        ul = ln.upper()
        nums = _extract_numbers_from_line(ln)
        if not nums:
            continue
        if ("PAIEMENT" in ul or "PAIMENTS" in ul or "REÇUS" in ul or "RECUS" in ul) and "RESTE" not in ul:
            big = [n for n in nums if n >= 5 and not _is_likely_year(n)]
            if big:
                paid = float(max(big))
        if "RESTE DU" in ul or "RESTE À" in ul or "RESTE A " in ul:
            small = [n for n in nums if n >= 0]
            if small:
                remaining = float(min(small))
            elif re.search(r"(?i)RESTE.+(0[.,]0+\b|\.0+\s*TND)", ln):
                remaining = 0.0
    return paid, remaining


def extract_supplier_block(ocr_text: str, transaction_type: str = "buy") -> Dict[str, Any]:
    """Bloc fournisseur (haut de page) : raison sociale courte + nom complet."""
    text = _glue_split_numeric_followups((ocr_text or "").strip())
    if not text:
        return {"supplier_name": "", "supplier_full_name": ""}
    issuer = _heur_find_supplier(text, transaction_type)
    short, full = _heur_supplier_split(issuer)
    return {"supplier_name": short or (issuer or "")[:80], "supplier_full_name": full or (issuer or "")[:240]}


def extract_client_block(ocr_text: str) -> Dict[str, Any]:
    """Bloc client après SOCIETE / CLIENT : nom, MF, ville."""
    text = _glue_split_numeric_followups((ocr_text or "").strip())
    if not text:
        return {}
    client_name = _heur_find_client_line(text) or ""
    tax = _heur_find_client_tax_id(text, client_name)
    city = _heur_find_client_city(text, client_name)
    return {
        "client_name": client_name or None,
        "client_tax_id": tax or None,
        "client_city": city or None,
    }


def extract_invoice_header(ocr_text: str) -> Dict[str, Any]:
    """N° facture, date facture, date échéance (heuristique déterministe)."""
    text = _glue_split_numeric_followups((ocr_text or "").strip())
    if not text:
        return {}
    inv = _heur_find_invoice_number(text)
    d_invoice = _heur_find_invoice_date(text)
    d_due = _heur_find_payment_due_date(text)
    return {
        "invoice_number": inv or None,
        "invoice_date": d_invoice or None,
        "payment_due_date": d_due or None,
    }


def extract_line_items_block(ocr_text: str) -> List[Dict[str, Any]]:
    """Parsing tableau articles : regex existantes + paires OCR ligne libellé / ligne chiffres."""
    raw = (ocr_text or "").strip()
    text = _glue_split_numeric_followups(raw)
    if not text:
        return []
    items = _heur_find_line_items(text)
    try:
        from app.services.invoice_table_parser import merge_parser_line_items

        return merge_parser_line_items(raw, text, items)
    except Exception:
        logger.debug("merge_parser_line_items fallback", exc_info=True)
        return items


def extract_totals_extended(ocr_text: str) -> Dict[str, Any]:
    """Totaux + paiement / reliquat détectés sur les libellés de bas de page."""
    text = _glue_split_numeric_followups((ocr_text or "").strip())
    if not text:
        return {}
    items = _heur_find_line_items(text)
    sub, tva, timbre, ttc = _heur_find_totals(text, items)
    paid, rem = _heur_find_paid_and_remaining(text)
    out: Dict[str, Any] = {
        "subtotal_htva": float(sub) if sub is not None else None,
        "tax_amount": float(tva) if tva is not None else None,
        "stamp_duty": float(timbre) if timbre is not None else None,
        "total_ttc": float(ttc) if ttc is not None else None,
        "amount_paid": float(paid) if paid is not None else None,
        "remaining_due": float(rem) if rem is not None else None,
    }
    return out


def _heur_find_invoice_date(text: str) -> str:
    m = _DATE_DM_RE.search(text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return ""


def _reconcile_qty_unit_line_total(q: float, pu: float, lt: float) -> tuple[float, float]:
    """Ajuste (qty, PU) si l’OCR mélange ordre des colonnes ou PU en « millimes » entiers."""
    if lt <= 0 or q <= 0 or pu < 0:
        return q, pu
    tol = max(2.0, lt * 0.08)

    def _ok(a: float, b: float) -> bool:
        return a > 0 and b >= 0 and abs(a * b - lt) <= tol

    candidates: list[tuple[float, float]] = []
    if _ok(q, pu):
        candidates.append((q, pu))
    if _ok(pu, q):
        candidates.append((pu, q))
    for qq, ppu in (
        (q, pu / 1000.0),
        (pu, q / 1000.0),
        (q / 1000.0, pu),
        (pu / 1000.0, q),
    ):
        if _ok(qq, ppu):
            candidates.append((qq, ppu))
    if not candidates:
        return q, pu

    def _score(qq: float, ppu: float) -> tuple[float, float]:
        """Higher is better; larger qty breaks ties (bulk agricultural lines)."""
        s = 0.0
        if 0.01 <= ppu <= 120 and qq >= 50:
            s += 120.0
        if 0.5 <= ppu <= 40 and qq >= 500:
            s += 80.0
        if qq >= 200 and qq >= ppu * 1.15:
            s += 40.0
        if qq < 150 and ppu > 200 and lt < 1_000_000:
            s -= 60.0
        err = abs(qq * ppu - lt) / max(lt, 1.0)
        return (s - err * 10.0, qq)

    best = max(candidates, key=lambda t: _score(t[0], t[1]))
    return round(best[0], 6), round(best[1], 6)


def _heur_find_line_items(text: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen: set[tuple[str, float]] = set()
    upper_ctx = (text[:5000]).upper()
    for line in text.splitlines():
        line_stripped = line.strip()
        if len(line_stripped) < 12:
            continue
        m = _LINE_ITEM_RE.match(line_stripped)
        if m:
            desig = _fix_line_designation_ocr(re.sub(r"\s+", " ", m.group(1).strip()), upper_ctx)
            q = _parse_amount_token(m.group(2))
            pu = _parse_amount_token(m.group(3))
            lt = _parse_amount_token(m.group(4))
            if q is None or pu is None:
                continue
            if lt is None:
                lt = round(q * pu, 3)
            if q and pu and lt:
                q, pu = _reconcile_qty_unit_line_total(float(q), float(pu), float(lt))
            if q <= 0 or pu < 0:
                continue
            if lt and abs(float(q) * float(pu) - float(lt)) > max(2.0, float(lt) * 0.08):
                continue
            key = (desig[:48], round(float(lt), 3))
            if key not in seen:
                seen.add(key)
                items.append(
                    {
                        "designation": desig[:200],
                        "quantity": float(q),
                        "unit_price": float(pu),
                        "line_total": float(lt),
                    }
                )
            continue
        # Product code / ref row: 613 ALCO … or CM1S Aliment … (STPA, Medimix)
        mcode = re.match(
            r"(?im)^\s*(?:\d{3}|[A-Z]{1,4}\d{1,5}[A-Z]?)\s+(.+)$",
            line_stripped,
        )
        if mcode:
            rest = mcode.group(1).strip()
            m_am = re.search(
                r"(?=(\d+,\d{2,4}(?!\d)|\d{1,3}(?:\s\d{3})+,\d+|\d{1,3}(?:\.\d{3})+\.\d+|\d{1,3}(?:\.\d{3})+,\d+))",
                rest,
            )
            if not m_am:
                continue
            desig = _fix_line_designation_ocr(
                rest[: m_am.start()].strip(),
                upper_ctx,
            )
            tail = rest[m_am.start() :].strip()
            if len(desig) < 2:
                continue
            desig = re.sub(r"\s+", " ", desig)
            vals = _amounts_from_spaced_tail(tail)
            picked = None
            if len(vals) >= 4:
                q, pu, lt = vals[-4], vals[-2], vals[-1]
                if lt >= 10 and abs(q * pu - lt) <= max(2.0, lt * 0.08):
                    picked = (q, pu, lt)
            if picked is None and len(vals) >= 3:
                a, b, lt = vals[-3], vals[-2], vals[-1]
                if lt >= 10 and abs(a * b - lt) <= max(2.0, lt * 0.08):
                    picked = (a, b, lt)
            if picked:
                a, b, lt = picked
                a, b = _reconcile_qty_unit_line_total(float(a), float(b), float(lt))
                key = (desig[:48], round(float(lt), 3))
                if key not in seen:
                    seen.add(key)
                    items.append(
                        {
                            "designation": desig[:200],
                            "quantity": float(a),
                            "unit_price": float(b),
                            "line_total": float(lt),
                        }
                    )
            continue
        # Loose row: label then 3+ numbers; last ≈ product of previous two (OCR order varies)
        if not re.search(r"[A-Za-zÀ-ÿ]{3,}", line_stripped):
            continue
        nums_raw = _AMT_TOKEN_RE.findall(line_stripped)
        vals = [v for x in nums_raw if (v := _parse_amount_token(x)) is not None and v > 0]
        if len(vals) < 3:
            continue
        des_m = re.match(r"^\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9\s%'\-]{2,180}?)\s+", line_stripped)
        if not des_m:
            continue
        desig = re.sub(
            r"\s+",
            " ",
            _fix_line_designation_ocr(des_m.group(1).strip(), upper_ctx),
        )
        a, b, lt = vals[-3], vals[-2], vals[-1]
        if lt < 10:
            continue
        a, b = _reconcile_qty_unit_line_total(float(a), float(b), float(lt))
        if abs(a * b - lt) > max(2.0, lt * 0.08):
            continue
        key = (desig[:48], round(float(lt), 3))
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "designation": desig[:200],
                "quantity": float(a),
                "unit_price": float(b),
                "line_total": float(lt),
            }
        )
    return items[:50]


def _heur_find_totals(
    text: str, items: List[Dict[str, Any]]
) -> tuple[float | None, float | None, float | None, float | None]:
    """
    Returns (subtotal_htva, tva_amount, timbre_amount, total_ttc).
    Timbre is kept separate so reports don't show 1.000 TND as \"TVA\".
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    ttc_vals: list[float] = []
    sub_vals: list[float] = []
    tva_vals: list[float] = []
    timbre_vals: list[float] = []
    items_sum = sum(float(it.get("line_total") or 0) for it in items)

    for ln in lines:
        ul = ln.upper()
        nums = _extract_numbers_from_line(ln)
        if not nums:
            continue
        if any(
            x in ul
            for x in (
                "RESTE DU",
                "RESTE À",
                "RESTE A ",
                "SOLDE A",
                "SOLDE:",
                "BALANCE ",
            )
        ):
            if max(nums) < 12:
                continue
        if any(
            k in ul
            for k in (
                "TOTAL TTC",
                "T.T.C",
                "TTC",
                "NET ",
                "NET À",
                "NET A",
                "MONTANT TTC",
                "TOTAL GENERAL",
                "TOTAL GÉNÉRAL",
                "À PAYER",
                "A PAYER",
                "PAIEMENTS RECUS",
                "PAIEMENTS REÇUS",
                "PAIMENTS RECUS",
                "PAYMENTS RECEIVED",
            )
        ) and "RESTE DU" not in ul:
            ttc_vals.extend(nums)
        if any(
            sk in ul
            for sk in (
                "SOUS-TOTAL",
                "SOUS TOTAL",
                "TOTAL HTVA",
                "TOTAL HT",
                "NET H.T",
                "NET HT",
                "NET H.T.",
                "TOTAL PRODUITS",
                "MONTANT HTVA",
            )
        ) or (("SOUS" in ul and "TOTAL" in ul) or ul.startswith("S-TOTAL")):
            sub_vals.extend(nums)
        if "TIMBRE" in ul or "DROIT DE TIMBRE" in ul or "TAXE TIMBRE" in ul:
            for n in nums:
                if 0 < n < 500:
                    timbre_vals.append(n)
        elif "TOTAL TVA" in ul or "MONTANT TVA" in ul:
            for n in nums:
                if 0 < n < 100000:
                    tva_vals.append(n)
        elif re.search(r"\bTVA\b", ul) and "TIMBRE" not in ul:
            big = [n for n in nums if n > 100]
            seq = big if big else nums
            pct_in_line = "%" in ul
            for n in seq:
                if n <= 0:
                    continue
                if pct_in_line and n < 35:
                    continue
                if 1 < n < 1000000:
                    tva_vals.append(n)

    def _pick_max_plausible_ttc(
        vals: list[float], floor: float = 20.0
    ) -> float | None:
        cand = [v for v in vals if v >= floor and not _is_likely_year(v)]
        if not cand:
            return None
        if items_sum >= 200:
            lo = max(floor, items_sum * 0.85)
            hi = items_sum * 1.18 + 15000.0
            plausible = [v for v in cand if lo <= v <= hi]
            if plausible:
                return float(max(plausible))
        cand_sorted = sorted(cand)
        if len(cand_sorted) >= 2 and cand_sorted[-1] > cand_sorted[-2] * 25:
            cand = [v for v in cand if v <= cand_sorted[-2] * 8]
            if not cand:
                cand = cand_sorted[:-1]
        return float(max(cand)) if cand else None

    def _pick_sub_max(vals: list[float], floor: float = 50.0) -> float | None:
        cand = [v for v in vals if v >= floor and not _is_likely_year(v)]
        if not cand:
            return None
        if items_sum >= 200:
            lo = items_sum * 0.85
            hi = items_sum * 1.05 + 5000.0
            plausible = [v for v in cand if lo <= v <= hi]
            if plausible:
                return float(max(plausible))
        return float(max(cand))

    ttc = _pick_max_plausible_ttc(ttc_vals, floor=20.0)
    subtotal = _pick_sub_max(sub_vals, floor=20.0)
    tva = max(tva_vals) if tva_vals else None
    timbre = max(timbre_vals) if timbre_vals else None

    if ttc is None:
        all_big: list[float] = []
        for ln in lines[-25:]:
            all_big.extend(
                n for n in _extract_numbers_from_line(ln) if n >= 100 and not _is_likely_year(n)
            )
        if all_big:
            ttc = _pick_max_plausible_ttc(all_big, floor=100.0)

    if subtotal is None and items:
        subtotal = sum(float(it.get("line_total") or 0) for it in items)
        if subtotal <= 0:
            subtotal = None

    add_tax = (tva or 0.0) + (timbre or 0.0)
    if ttc is None and subtotal is not None and add_tax > 0:
        ttc = float(subtotal) + add_tax
    elif ttc is None and subtotal is not None:
        ttc = float(subtotal)

    return subtotal, tva, timbre, ttc


def heuristic_invoice_from_ocr(
    ocr_text: str, transaction_type: str = "buy"
) -> Dict[str, Any]:
    """Build partial invoice dict from OCR regex/heuristics (no LLM)."""
    raw_ocr = (ocr_text or "").strip()
    if not raw_ocr:
        return {}
    text = _glue_split_numeric_followups(raw_ocr)
    sb = extract_supplier_block(text, transaction_type)
    cb = extract_client_block(text)
    hd = extract_invoice_header(text)
    items = _heur_find_line_items(text)
    totals_ex = extract_totals_extended(text)

    currency = "TND"
    if re.search(r"\bEUR\b", text, re.I):
        currency = "EUR"
    elif re.search(r"\bUSD\b", text, re.I):
        currency = "USD"
    if re.search(r"\bTND\b|\bMILLIM|DEN\b|دينار", text, re.I):
        currency = "TND"

    doc_type = _heur_document_type_from_text(raw_ocr)
    sup_phone = _heur_supplier_phone(raw_ocr)
    sup_tax = _heur_supplier_tax_id_top(raw_ocr)
    sup_city = _heur_supplier_city_after_phone(raw_ocr)
    tax_rate = _heur_tax_rate_percent(raw_ocr)

    pay_due = hd.get("payment_due_date") or ""
    inv_date = hd.get("invoice_date") or ""
    # Si l’OCR ne montre qu’une date de facture (souvent identique à l’échéance affichée ailleurs)
    if (inv_date or "").strip() and not (pay_due or "").strip():
        pay_due = inv_date

    out: Dict[str, Any] = {
        "document_type": doc_type,
        "supplier_name": sb.get("supplier_name") or None,
        "supplier_full_name": sb.get("supplier_full_name") or None,
        "supplier_tax_id": sup_tax or None,
        "supplier_phone": sup_phone or None,
        "supplier_address": sup_city or None,
        "tax_rate_percent": tax_rate,
        "client_name": cb.get("client_name"),
        "client_tax_id": cb.get("client_tax_id"),
        "client_city": cb.get("client_city"),
        "invoice_number": hd.get("invoice_number") or "",
        "invoice_date": inv_date or "",
        "payment_due_date": pay_due or None,
        "items": items,
        "subtotal_htva": totals_ex.get("subtotal_htva"),
        "tax_amount": totals_ex.get("tax_amount"),
        "stamp_duty": totals_ex.get("stamp_duty"),
        "total_ttc": totals_ex.get("total_ttc"),
        "amount_paid": totals_ex.get("amount_paid"),
        "remaining_due": totals_ex.get("remaining_due"),
        "currency": currency,
    }
    return out


def merge_heuristic_into_extracted(
    extracted: Dict[str, Any],
    ocr_text: str,
    transaction_type: str = "buy",
) -> Dict[str, Any]:
    """Fill missing or zeroed fields from OCR heuristics after LLM (or fallback)."""
    if not ocr_text or not str(ocr_text).strip():
        return extracted
    if not isinstance(extracted, dict):
        extracted = {}

    ex = _apply_invoice_defaults(dict(extracted))
    heur = heuristic_invoice_from_ocr(ocr_text, transaction_type)

    def _nonzero_ttc(d: Dict) -> float:
        try:
            return float(d.get("total_ttc") or 0)
        except (TypeError, ValueError):
            return 0.0

    ttc_before = _nonzero_ttc(ex)
    had_error = bool(ex.get("extraction_error"))
    filled = False

    if heur.get("supplier_name") and not (ex.get("supplier_name") or "").strip():
        ex["supplier_name"] = heur["supplier_name"]
        filled = True
    if (
        heur.get("supplier_name")
        and (transaction_type or "buy").lower() == "buy"
    ):
        hs = (heur.get("supplier_name") or "").strip()
        es = (ex.get("supplier_name") or "").strip()
        if hs and es and es.upper() != hs.upper() and "ABBES" in es.upper() and "ABBES" not in hs.upper():
            ex["supplier_name"] = hs
            filled = True
    if heur.get("invoice_number") and not (ex.get("invoice_number") or "").strip():
        ex["invoice_number"] = heur["invoice_number"]
        filled = True
    if heur.get("invoice_date") and not (ex.get("invoice_date") or "").strip():
        ex["invoice_date"] = heur["invoice_date"]
        filled = True

    if heur.get("items") and not ex.get("items"):
        ex["items"] = heur["items"]
        filled = True

    ttc_h = _nonzero_ttc(heur)
    if ttc_h > 0 and ttc_before <= 0:
        ex["total_ttc"] = ttc_h
        filled = True

    sub_h = float(heur.get("subtotal_htva") or 0)
    if sub_h > 0 and float(ex.get("subtotal_htva") or 0) <= 0:
        ex["subtotal_htva"] = sub_h
        filled = True

    tax_h = float(heur.get("tax_amount") or 0)
    if tax_h > 0 and float(ex.get("tax_amount") or 0) <= 0:
        ex["tax_amount"] = tax_h
        filled = True

    stamp_h = float(heur.get("stamp_duty") or 0)
    if stamp_h > 0 and float(ex.get("stamp_duty") or 0) <= 0:
        ex["stamp_duty"] = stamp_h
        filled = True
    if (
        stamp_h > 0
        and abs(float(ex.get("tax_amount") or 0) - stamp_h) < 0.001
        and float(heur.get("tax_amount") or 0) <= 0
    ):
        ex["tax_amount"] = 0.0
        ex["stamp_duty"] = stamp_h
        filled = True

    if (
        heur.get("currency")
        and heur["currency"] != "TND"
        and (ex.get("currency") in ("", "TND", None))
    ):
        ex["currency"] = heur["currency"]

    if filled:
        try:
            prev_conf = float(ex.get("confidence") or 0.0)
        except (TypeError, ValueError):
            prev_conf = 0.0
        ex["confidence"] = max(prev_conf, 0.38)
        if had_error and (
            (ex.get("supplier_name") or "").strip()
            or _nonzero_ttc(ex) > 0
            or ex.get("items")
        ):
            ex.pop("extraction_error", None)
        ex.setdefault("extraction_method", "llm_plus_heuristic")

    sn = (ex.get("supplier_name") or "").strip()
    if sn:
        ex["supplier_name"] = _sanitize_supplier_name(sn)

    return ex


def reconcile_extracted_invoice_numbers(
    extracted: Dict[str, Any],
    ocr_text: str | None = None,
    transaction_type: str = "buy",
) -> Dict[str, Any]:
    """
    Fix inconsistent totals vs line items, move timbre out of tax_amount, clean supplier.
    Called after LLM + heuristics so PDF/preview stay logically consistent.
    """
    if not isinstance(extracted, dict):
        return extracted
    ex = dict(extracted)

    sn = (ex.get("supplier_name") or "").strip()
    if sn:
        ex["supplier_name"] = _sanitize_supplier_name(sn)

    try:
        stamp = float(ex.get("stamp_duty") or 0)
        tax = float(ex.get("tax_amount") or 0)
        if stamp <= 0 and 0 < tax <= 5.0:
            ex["stamp_duty"] = tax
            ex["tax_amount"] = 0.0
    except (TypeError, ValueError):
        pass

    items = [i for i in (ex.get("items") or []) if isinstance(i, dict)]
    items_sum = sum(float(i.get("line_total") or 0) for i in items)

    try:
        ttc = float(ex.get("total_ttc") or 0)
        sub = float(ex.get("subtotal_htva") or 0)
        stamp_f = float(ex.get("stamp_duty") or 0)
        tax_f = float(ex.get("tax_amount") or 0)
    except (TypeError, ValueError):
        return ex

    if items_sum > 200:
        if (
            ttc > items_sum * 15
            or (ttc > 2_000_000 and items_sum < 500_000)
            or (ttc < items_sum * 0.5 and ttc > 0 and items_sum > 1000)
        ):
            ex["total_ttc"] = round(items_sum + stamp_f + tax_f, 3)
            ttc = float(ex["total_ttc"])
        if sub <= 0 or sub > items_sum * 1.02 + 5 or sub < items_sum * 0.4:
            ex["subtotal_htva"] = round(items_sum, 3)
            sub = float(ex["subtotal_htva"])
        expected = sub + stamp_f + tax_f
        if (
            expected > 100
            and ttc > expected * 1.05
            and abs(ttc - (items_sum + stamp_f + tax_f)) > max(50.0, items_sum * 0.02)
        ):
            alt = items_sum + stamp_f + tax_f
            if alt > 0:
                ex["total_ttc"] = round(alt, 3)
    elif (
        items_sum <= 0
        and ocr_text
        and len(ocr_text.strip()) > 80
        and ttc > 500_000
    ):
        heur_snap = heuristic_invoice_from_ocr(ocr_text, (transaction_type or "buy").lower())
        try:
            h_ttc = float(heur_snap.get("total_ttc") or 0)
        except (TypeError, ValueError):
            h_ttc = 0.0
        if 50 < h_ttc < min(ttc, 5_000_000):
            ex["total_ttc"] = round(h_ttc, 3)
            hs = float(heur_snap.get("subtotal_htva") or 0)
            if hs > 0:
                ex["subtotal_htva"] = round(hs, 3)
            hd = float(heur_snap.get("stamp_duty") or 0)
            ht = float(heur_snap.get("tax_amount") or 0)
            if hd > 0:
                ex["stamp_duty"] = hd
            if ht >= 0:
                ex["tax_amount"] = ht
    return ex


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
    obj.setdefault("supplier_name", "")
    obj.setdefault("invoice_number", "")
    obj.setdefault("invoice_date", "")
    obj.setdefault("subtotal_htva", 0.0)
    obj.setdefault("tax_amount", 0.0)
    obj.setdefault("stamp_duty", 0.0)
    obj.setdefault("total_ttc", 0.0)
    obj.setdefault("currency", "TND")
    if isinstance(obj.get("totals"), dict):
        t = obj["totals"]
        try:
            if float(obj.get("total_ttc") or 0) == 0 and t.get("ttc") is not None:
                obj["total_ttc"] = float(t["ttc"])
        except (TypeError, ValueError):
            pass
        try:
            if float(obj.get("subtotal_htva") or 0) == 0 and t.get("htva") is not None:
                obj["subtotal_htva"] = float(t["htva"])
        except (TypeError, ValueError):
            pass
        try:
            if float(obj.get("tax_amount") or 0) == 0 and t.get("tva") is not None:
                obj["tax_amount"] = float(t["tva"])
        except (TypeError, ValueError):
            pass
        try:
            if float(obj.get("stamp_duty") or 0) == 0 and t.get("timbre") is not None:
                obj["stamp_duty"] = float(t["timbre"])
        except (TypeError, ValueError):
            pass

    for f in ("supplier_name", "invoice_number", "invoice_date"):
        v = obj.get(f)
        obj[f] = str(v).strip() if v is not None else ""

    inv_year = _infer_year_from_invoice_number(obj["invoice_number"])
    if inv_year and obj["invoice_date"]:
        try:
            date_year = int(obj["invoice_date"][:4])
            if date_year != inv_year and abs(date_year - inv_year) > 1:
                logger.info(
                    "invoice_date year %d ≠ invoice_number year %d → clearing date",
                    date_year,
                    inv_year,
                )
                obj["invoice_date"] = ""
        except (ValueError, TypeError):
            pass

    if not obj.get("currency"):
        obj["currency"] = "TND"

    for f in ("subtotal_htva", "tax_amount", "total_ttc", "stamp_duty"):
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

        qty, pu, lt = item["quantity"], item["unit_price"], item["line_total"]
        if qty > 0 and pu > 0 and lt == 0:
            item["line_total"] = round(qty * pu, 3)
        elif qty > 0 and lt > 0 and pu == 0:
            item["unit_price"] = round(lt / qty, 3)
        elif pu > 0 and lt > 0 and qty == 0:
            item["quantity"] = round(lt / pu, 3)

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


def normalize_extracted_invoice_dict(extracted: Dict) -> Dict:
    """
    LLM schema uses flat subtotal_htva / tax_amount / total_ttc; PDF and API preview
    expect nested totals.{htva,tva,ttc}. Merge so mobile preview and list totals work.
    """
    if not isinstance(extracted, dict):
        return extracted
    out = dict(extracted)
    totals = dict(out.get("totals") or {})

    def _set_t(key: str, val: Any) -> None:
        if val is None:
            return
        try:
            totals[key] = float(val)
        except (TypeError, ValueError):
            pass

    if totals.get("htva") is None:
        _set_t("htva", out.get("subtotal_htva"))
    if totals.get("tva") is None:
        _set_t("tva", out.get("tax_amount"))
    if totals.get("timbre") is None:
        _set_t("timbre", out.get("stamp_duty"))
    if totals.get("ttc") is None:
        _set_t("ttc", out.get("total_ttc"))

    out["totals"] = totals
    return out


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


def _groq_parse_content(content: str, ocr_text: str = "") -> Dict:
    raw = (content or "").strip()
    try:
        return _apply_invoice_defaults(json.loads(raw), ocr_text=ocr_text)
    except json.JSONDecodeError:
        obj = _parse_json_from_response(raw)
        return _apply_invoice_defaults(obj, ocr_text=ocr_text)


async def _extract_invoice_groq(ocr_text: str, transaction_type: str) -> Dict:
    """Extract invoice fields using Groq."""
    from groq import Groq

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "8192"))

    client = Groq(api_key=api_key)

    preprocessed = _preprocess_ocr_for_llm(ocr_text)
    user_content = f"TRANSACTION TYPE: {transaction_type}\nOCR TEXT:\n{preprocessed}"

    def _parse_groq_response(raw_content: str) -> Dict:
        fixed = _eval_json_arithmetic(raw_content)
        obj = _parse_json_from_response(fixed)
        return _apply_invoice_defaults(obj, ocr_text=ocr_text)

    last_err: Exception | None = None
    for attempt in range(2):
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": INVOICE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                model=model,
                max_tokens=max_tokens,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = chat_completion.choices[0].message.content
            if not content:
                raise RuntimeError("Groq returned empty content")
            return _parse_groq_response(content)
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            logger.warning(
                "Groq invoice JSON parse attempt %d failed: %s", attempt + 1, str(e)[:200]
            )
        except Exception as e:
            last_err = e
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
            logger.warning(
                "Groq invoice extraction failed (%s), using fallback", str(e)[:300]
            )
            break
    if last_err:
        logger.warning("Groq giving up after error: %s", str(last_err)[:200])
    return _fallback_invoice_extraction(ocr_text)


async def extract_invoice_fields(ocr_text: str, transaction_type: str) -> Dict:
    """
    Extract structured invoice fields from OCR text using LLM.
    
    transaction_type: "sell" | "buy" — context for better accuracy.
    Provider: LLM_PROVIDER env var (ollama | openai | mcp | groq | fallback).
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    ocr_len = len(ocr_text or "")

    result: Dict[str, Any]
    try:
        if provider == "ollama":
            result = await _extract_invoice_ollama(ocr_text, transaction_type)
        elif provider == "openai":
            result = await _extract_invoice_openai(ocr_text, transaction_type)
        elif provider == "mcp":
            try:
                result = await _extract_invoice_mcp(ocr_text, transaction_type)
            except Exception as e:
                logger.warning("MCP invoice extraction failed (%s), using fallback", e)
                result = _fallback_invoice_extraction(ocr_text)
        elif provider == "groq":
            result = await _extract_invoice_groq(ocr_text, transaction_type)
        elif provider == "fallback":
            logger.info("Using fallback extraction (no LLM provider configured)")
            result = _apply_invoice_defaults({
                "items": [],
                "currency": "TND",
                "extraction_method": "fallback_due_to_no_provider",
            })
        else:
            raise RuntimeError(f"Unknown LLM_PROVIDER: {provider!r}")
    except Exception as e:
        logger.error("LLM extraction failed for provider %s: %s", provider, e)
        if provider == "ollama":
            logger.warning("Ollama not available, likely missing dependencies. Using fallback.")
        elif provider == "groq":
            logger.warning("Groq not available, likely missing dependencies. Using fallback.")
        elif provider == "openai":
            logger.warning("OpenAI not available, likely missing dependencies. Using fallback.")
        result = _fallback_invoice_extraction(ocr_text)

    merged = merge_heuristic_into_extracted(result, ocr_text or "", transaction_type)

    def _extraction_signature(d: Dict[str, Any]) -> tuple[int, int, float]:
        if not isinstance(d, dict):
            return (0, 0, 0.0)
        sup = 1 if (d.get("supplier_name") or "").strip() else 0
        n_it = len(d.get("items") or [])
        try:
            ttc = float(d.get("total_ttc") or 0)
        except (TypeError, ValueError):
            ttc = 0.0
        return (sup, n_it, ttc)

    if merged.get("extraction_error") and ocr_len > 60:
        h_pure = heuristic_invoice_from_ocr(ocr_text or "", transaction_type)
        if _extraction_signature(h_pure) > _extraction_signature(merged):
            merged = _apply_invoice_defaults(dict(h_pure))
            merged["confidence"] = max(float(merged.get("confidence") or 0), 0.5)
            merged.pop("extraction_error", None)
            merged["extraction_method"] = "heuristic_preferred_after_llm_failure"

    merged = reconcile_extracted_invoice_numbers(
        merged, ocr_text or "", transaction_type
    )

    try:
        ttc = float(merged.get("total_ttc") or 0)
        n_items = len(merged.get("items") or [])
        sup = (merged.get("supplier_name") or "")[:40]
        logger.info(
            "Invoice extraction provider=%s ocr_len=%d items=%d total_ttc=%s supplier=%r",
            provider,
            ocr_len,
            n_items,
            ttc,
            sup,
        )
    except (TypeError, ValueError):
        logger.info("Invoice extraction provider=%s ocr_len=%d (totals log skipped)", provider, ocr_len)
    return merged


async def extract_invoice_from_ocr(
    ocr_text: str, transaction_type: str
) -> tuple[Dict[str, Any], float]:
    """Returns (extracted_dict, confidence_float) for legacy callers."""
    extracted = await extract_invoice_fields(ocr_text, transaction_type)
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
    return extracted, float(extracted.get("confidence") or confidence)
