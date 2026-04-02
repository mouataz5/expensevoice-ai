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
Amount format: dots group thousands, comma is decimals/millimes (e.g. 15.576,000 TND = 15576.000 TND).
May appear as 15.576.000 (two dot patterns) — treat as 15576.000 in TND context.

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

# --- Heuristic extraction from raw OCR (FR / TN invoices when LLM fails) ---

_SUPPLIER_LINE_RE = re.compile(
    r"(?im)^\s*(STE|SARL|EURL|ETS|S\.?\s*A\.?\s*R\.?\s*L\.?)\s+(.{3,120})\s*$"
)
_DATE_DM_RE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b")
_INV_NUM_RE = re.compile(
    r"(?i)(?:n[o°]\s*facture|facture\s*n[o°]|facture|n[o°]|n\.|réf|ref)\s*[:\s]?\s*([A-Z0-9][A-Z0-9\-/]{4,30})"
)
_INV_FA_REF_RE = re.compile(r"\b(FA\d{2,8}/\d{4})\b", re.I)
_LINE_ITEM_RE = re.compile(
    r"(?im)^\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9\s%'\-]{2,45}?)\s+"
    r"(\d[\d\s.,]{1,14})\s+(\d[\d\s.,]{1,14})\s+(\d[\d\s.,]{1,16})\s*$"
)


def _parse_amount_token(raw: str) -> float | None:
    """Parse FR/TN amounts: 15.575,000, 15 575,000, 22 176,003, 15,575.000."""
    if not raw or not str(raw).strip():
        return None
    t = str(raw).strip().replace("\u00a0", " ")
    t = re.sub(r"(?i)TND|EUR|USD|DT|DNT|QX\b", "", t).strip()
    if not t or not any(c.isdigit() for c in t):
        return None
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
    r"\d{1,3}(?:\s\d{3})+,\d+|\d{1,3}(?:\.\d{3})+,\d+|\d{1,3}(?:\.\d{3})+\.\d+"
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
        if re.search(r"(?i)ABBES", s) and re.search(
            r"(?i)STE|SARL|VOLAILLE|POUR", s
        ):
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
    return client or ""


def _heur_find_invoice_number(text: str) -> str:
    m = _INV_FA_REF_RE.search(text)
    if m:
        return m.group(1).strip()[:80]
    m = _INV_NUM_RE.search(text)
    if m:
        return m.group(1).strip()[:80]
    return ""


def _heur_find_invoice_date(text: str) -> str:
    m = _DATE_DM_RE.search(text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return ""


def _heur_find_line_items(text: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen: set[tuple[str, float]] = set()
    for line in text.splitlines():
        line_stripped = line.strip()
        if len(line_stripped) < 12:
            continue
        m = _LINE_ITEM_RE.match(line_stripped)
        if m:
            desig = re.sub(r"\s+", " ", m.group(1).strip())
            q = _parse_amount_token(m.group(2))
            pu = _parse_amount_token(m.group(3))
            lt = _parse_amount_token(m.group(4))
            if q is None or pu is None:
                continue
            if lt is None:
                lt = round(q * pu, 3)
            if q and pu and lt and abs(q * pu - lt) > max(2.0, lt * 0.08):
                q, pu = pu, q
            if q <= 0 or pu < 0:
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
            desig = rest[: m_am.start()].strip()
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
        des_m = re.match(r"^\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9\s%'\-]{2,45}?)\s+", line_stripped)
        if not des_m:
            continue
        desig = re.sub(r"\s+", " ", des_m.group(1).strip())
        a, b, lt = vals[-3], vals[-2], vals[-1]
        if lt < 10:
            continue
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
            for n in nums:
                if 1 < n < 100000:
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
    text = (ocr_text or "").strip()
    if not text:
        return {}
    text = _glue_split_numeric_followups(text)
    supplier = _heur_find_supplier(text, transaction_type)
    client_line = _heur_find_client_line(text)
    invoice_number = _heur_find_invoice_number(text)
    invoice_date = _heur_find_invoice_date(text)
    items = _heur_find_line_items(text)
    subtotal, tva, timbre, ttc = _heur_find_totals(text, items)

    currency = "TND"
    if re.search(r"\bEUR\b", text, re.I):
        currency = "EUR"
    elif re.search(r"\bUSD\b", text, re.I):
        currency = "USD"

    out: Dict[str, Any] = {
        "supplier_name": supplier,
        "client_name": client_line or None,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "items": items,
        "subtotal_htva": float(subtotal) if subtotal is not None else None,
        "tax_amount": float(tva) if tva is not None else None,
        "stamp_duty": float(timbre) if timbre is not None else None,
        "total_ttc": float(ttc) if ttc is not None else None,
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
    obj.setdefault("stamp_duty", 0.0)
    obj.setdefault("total_ttc", 0.0)
    obj.setdefault("currency", "TND")
    # LLM may return only nested totals
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
            q, pu = float(item["quantity"] or 0), float(item["unit_price"] or 0)
            lt = float(item.get("line_total") or 0)
            if q and pu and lt <= 0:
                item["line_total"] = round(q * pu, 3)
            cleaned_items.append(item)
    
    obj["items"] = cleaned_items
    
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


def _groq_parse_content(content: str) -> Dict:
    raw = (content or "").strip()
    try:
        return _apply_invoice_defaults(json.loads(raw))
    except json.JSONDecodeError:
        obj = _parse_json_from_response(raw)
        return _apply_invoice_defaults(obj)


async def _extract_invoice_groq(ocr_text: str, transaction_type: str) -> Dict:
    """Extract invoice fields using Groq."""
    from groq import Groq

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "8192"))

    client = Groq(api_key=api_key)

    user_content = f"TRANSACTION TYPE: {transaction_type}\nOCR TEXT:\n{ocr_text}"

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
            return _groq_parse_content(content)
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            logger.warning(
                "Groq invoice JSON parse attempt %d failed: %s", attempt + 1, str(e)[:200]
            )
        except Exception as e:
            last_err = e
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
