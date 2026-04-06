"""
Parser déterministe de tableaux articles depuis OCR (factures TN / FR).

Complète les regex existantes : paires « ligne libellé » + « ligne de chiffres »,
heuristique sur 3 montants, normalisation TND, validation financière légère.
"""
from __future__ import annotations

import re
from typing import Any

from app.utils.money import normalize_tnd_amount

__all__ = [
    "normalize_tnd_amount",
    "detect_currency",
    "parse_line_numbers",
    "detect_invoice_table_lines",
    "detect_invoice_table_lines_debug",
    "fix_line_item",
    "line_items_from_table_detection",
    "merge_parser_line_items",
    "extract_totals_from_text",
    "validate_financials",
    "detect_table_region_from_ocr",
    "extract_table_headers",
    "parse_table_rows",
    "normalize_financial_columns",
    "validate_table_math",
]

_TABLE_START_RE = re.compile(
    r"(?i)\b("
    r"ARTICLE|DESIGNATION|DÉSIGNATION|DESIGNATION|LIBELLE|LIBELLÉ|"
    r"RÉF\.?\s*ART|REF\.?\s*ART|CODE\s*ART|Désignation"
    r")\b"
)
_TABLE_END_RE = re.compile(
    r"(?i)\b("
    r"SOUS-TOTAL|TOTAL\s+PRODUIT|TOTAL\s+HTVA|TOTAL\s+HT\b|"
    r"NET\s+À\s+PAYER|NET\s+A\s+PAYER|TOTAL\s+TTC|"
    r"PAIEMENTS?\s+RECUS|PAIEMENTS?\s+REÇUS|RESTE\s+DU"
    r")\b"
)
_SKIP_LINE_START = re.compile(
    r"(?i)^(total|sous|tva|timbre|net|facture|date|n°|n\.|n[o°]|réf|ref|client|societe|mf|matricule|bon\s+de)\b"
)
_TN_INVOICE_HINT = re.compile(
    r"(?i)\b(TND|SOUS-TOTAL|TAXE\s+TIMBRE|MATRICULE\s+FISCAL|AMEN\s+FINANCE)\b|د\.ت"
)


def _ie():
    from app.services import invoice_extraction as ie

    return ie


def _amount_tokens_from_mixed_line(line: str) -> list[float]:
    """Nombres sur une ligne « libellé + PU + qté + total » (finditer rate trop court)."""
    ie = _ie()
    parts = re.split(r"\s+", (line or "").strip())
    out: list[float] = []
    for p in parts:
        if not p or not any(c.isdigit() for c in p):
            continue
        v = ie._parse_amount_token(p)
        if v is None or ie._is_likely_year(float(v)):
            continue
        out.append(float(v))
    return out


def detect_currency(ocr_text: str) -> str:
    """Devise document ; signaux tunisiens → TND, jamais EUR par défaut arbitraire."""
    raw = ocr_text or ""
    ul = raw.upper()
    if "TND" in ul or "د.ت" in raw or re.search(r"\bDT\b", ul) or "DINAR" in ul:
        return "TND"
    if "DNT" in ul or "MILLIME" in ul or "MILLIMES" in ul:
        return "TND"
    if "EUR" in ul or "€" in raw:
        return "EUR"
    if "USD" in ul or re.search(r"\bUS\$\b", ul) or "$" in raw:
        return "USD"
    if _TN_INVOICE_HINT.search(raw):
        return "TND"
    return "TND"


def parse_line_numbers(numbers_list: list[float]) -> dict[str, Any] | None:
    """
    Mappe des nombres extraits vers (unit_price, quantity, line_subtotal).

    - Exactement 3 nombres : tri croissant → petit = PU, médian = qté, grand = sous-total.
    - Plus de 3 : trois derniers selon l’ordre OCR (colonnes fin de ligne), puis réconciliation.
    """
    nums = [float(x) for x in numbers_list if x is not None and float(x) > 0]
    if len(nums) < 3:
        return None
    if len(nums) == 3:
        lo, mid, hi = sorted(nums)
        return {
            "unit_price": float(lo),
            "quantity": float(mid),
            "line_subtotal": float(hi),
            "mapping": "sorted_triplet",
        }
    a, b, c = float(nums[-3]), float(nums[-2]), float(nums[-1])
    return {
        "unit_price": a,
        "quantity": b,
        "line_subtotal": c,
        "mapping": "ocr_tail_triplet",
    }


def _product_stub_from_numbers_line(numbers_line: str) -> str:
    """Libellé en tête de ligne « … 1825 6600 12.045.000 »."""
    s = (numbers_line or "").strip()
    if not s:
        return ""
    m = re.match(
        r"^(.+?)\s+(\d[\d\s.,]{1,16})\s+(\d[\d\s.,]{1,16})\s+(\d[\d\s.,]{1,18})\s*$",
        s,
        re.I,
    )
    if not m:
        return ""
    stub = re.sub(r"\s+", " ", m.group(1).strip())
    if len(stub) < 2 or not re.search(r"[A-Za-zÀ-ÿ]", stub):
        return ""
    return stub[:200]


def detect_invoice_table_lines(ocr_text: str) -> list[dict[str, Any]]:
    """
    Zone optionnelle entre libellé de colonnes (ARTICLE…) et SOUS-TOTAL / TOTAL…
    puis repérage de paires « texte » + « ligne à 3+ montants ».
    """
    ie = _ie()
    lines = [ln.rstrip() for ln in (ocr_text or "").splitlines()]
    n = len(lines)
    start_idx, end_idx = 0, n

    first_hdr: int | None = None
    for i, ln in enumerate(lines):
        if _TABLE_START_RE.search(ln or ""):
            first_hdr = i
            break
    if first_hdr is not None:
        start_idx = first_hdr + 1
        for j in range(start_idx, n):
            if _TABLE_END_RE.search(lines[j] or ""):
                end_idx = j
                break

    rows: list[dict[str, Any]] = []
    i = start_idx
    while i < end_idx:
        cur = (lines[i] or "").strip()
        nxt = (lines[i + 1] or "").strip() if i + 1 < end_idx else ""

        if not cur:
            i += 1
            continue
        if _SKIP_LINE_START.match(cur) or _TABLE_END_RE.search(cur):
            i += 1
            continue

        if nxt and len(cur) >= 3:
            nums_cur = ie._extract_numbers_from_line(cur)
            tally_n = ie._space_separated_amount_tally(nxt)
            has_label = bool(re.search(r"[A-Za-zÀ-ÿ]{3,}", cur))
            if (
                has_label
                and len(nums_cur) < 2
                and tally_n >= 3
                and not ie._glue_skip_client_or_table_boundary(cur, nxt)
            ):
                nums = ie._extract_numbers_from_line(nxt)
                if len(nums) < 3:
                    nums = _amount_tokens_from_mixed_line(nxt)
                nums = [
                    float(x)
                    for x in nums
                    if x is not None and not ie._is_likely_year(float(x))
                ]
                if len(nums) >= 3:
                    stub = _product_stub_from_numbers_line(nxt)
                    rows.append(
                        {
                            "description": cur,
                            "numbers_line": nxt,
                            "raw_numbers": nums,
                            "line_index": i,
                            "product_stub": stub,
                        }
                    )
                    i += 2
                    continue

        i += 1

    return rows


def detect_invoice_table_lines_debug(ocr_text: str) -> dict[str, Any]:
    """Même détection + bornes de zone, trace lisible pour debug pipeline."""
    ie = _ie()
    lines = [ln.rstrip() for ln in (ocr_text or "").splitlines()]
    n = len(lines)
    start_idx, end_idx = 0, n
    first_hdr = None
    for i, ln in enumerate(lines):
        if _TABLE_START_RE.search(ln or ""):
            first_hdr = i
            break
    if first_hdr is not None:
        start_idx = first_hdr + 1
        for j in range(start_idx, n):
            if _TABLE_END_RE.search(lines[j] or ""):
                end_idx = j
                break
    rows = detect_invoice_table_lines(ocr_text)
    trace: list[str] = []
    for row in rows:
        trace.append(
            f"L{row.get('line_index', 0) + 1}: mapping={parse_line_numbers(row['raw_numbers'])!r} "
            f"stub={row.get('product_stub')!r}"
        )
    return {
        "bounds": (start_idx, end_idx),
        "rows": rows,
        "trace": trace,
    }


def fix_line_item(
    item: dict[str, Any],
    *,
    ocr_text: str = "",
    neighbor_descriptions: list[str] | None = None,
) -> dict[str, Any]:
    """Cohérence qty × PU ≈ total, réconciliation millimes, enrichissement libellé OCR voisin."""
    ie = _ie()
    des = (item.get("designation") or item.get("description") or "").strip()
    q = float(item.get("quantity") or 0)
    pu = float(item.get("unit_price") or 0)
    lt = float(item.get("line_total") or item.get("line_subtotal") or 0)

    upper_ctx = (ocr_text or "")[:5000].upper()
    if neighbor_descriptions and (len(des) < 8 or re.match(r"(?i)^ate\b", des)):
        for nb in neighbor_descriptions:
            nb = (nb or "").strip()
            if len(nb) > len(des) and len(nb) >= 6:
                des = nb
                break

    des = ie._fix_line_designation_ocr(re.sub(r"\s+", " ", des), upper_ctx)

    if lt <= 0 and q > 0 and pu > 0:
        lt = round(q * pu, 3)
    elif q <= 0 and lt > 0 and pu > 0:
        q = round(lt / pu, 6)
    elif pu <= 0 and lt > 0 and q > 0:
        pu = round(lt / q, 6)

    if lt > 0 and q > 0 and pu > 0:
        q, pu = ie._reconcile_qty_unit_line_total(q, pu, lt)

    tol = max(2.0, lt * 0.08) if lt > 0 else 2.0
    if lt > 0 and q > 0 and pu > 0 and abs(q * pu - lt) > tol:
        lt = round(q * pu, 3)

    out: dict[str, Any] = {
        "designation": des[:200] if des else (item.get("designation") or "")[:200],
        "quantity": float(q),
        "unit_price": float(pu),
        "line_total": float(lt),
    }
    if item.get("details"):
        out["details"] = str(item.get("details"))[:500]
    return out


def _rows_to_line_items(rows: list[dict[str, Any]], ocr_text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        nums = row.get("raw_numbers") or []
        parsed = parse_line_numbers([float(x) for x in nums])
        if not parsed:
            continue
        stub = (row.get("product_stub") or "").strip()
        desc_line = (row.get("description") or "").strip()
        if stub:
            designation = stub
            details = (
                desc_line
                if desc_line and desc_line.lower() not in stub.lower()
                else None
            )
        else:
            designation = desc_line
            details = None
        item: dict[str, Any] = {
            "designation": designation,
            "quantity": parsed["quantity"],
            "unit_price": parsed["unit_price"],
            "line_total": parsed["line_subtotal"],
        }
        if details:
            item["details"] = details
        neigh = [desc_line] if desc_line and stub else None
        out.append(fix_line_item(item, ocr_text=ocr_text, neighbor_descriptions=neigh))
    return out


def line_items_from_table_detection(ocr_text: str) -> list[dict[str, Any]]:
    """Convertit `detect_invoice_table_lines` en items `designation` / qty / PU / line_total."""
    return _rows_to_line_items(detect_invoice_table_lines(ocr_text), ocr_text)


def merge_parser_line_items(
    ocr_raw: str,
    glued_text: str,
    existing: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Fusionne les lignes détectées par paires texte+nombres : évite les doublons
    (même total + même qté arrondie) et préfère une désignation plus courte si équivalente.
    """
    _ = glued_text  # signature stable pour le pipeline
    extra = line_items_from_table_detection(ocr_raw)

    def _sig(it: dict[str, Any]) -> tuple[float, float]:
        return (
            round(float(it.get("line_total") or 0), 1),
            round(float(it.get("quantity") or 0), 0),
        )

    out = list(existing)
    index_by_sig: dict[tuple[float, float], int] = {_sig(it): i for i, it in enumerate(out)}
    for it in extra:
        s = _sig(it)
        if s in index_by_sig:
            i = index_by_sig[s]
            cur = out[i]
            la, lb = len(it.get("designation") or ""), len(cur.get("designation") or "")
            if la and la < lb - 8:
                out[i] = it
            continue
        index_by_sig[s] = len(out)
        out.append(it)
    return out


def extract_totals_from_text(ocr_text: str) -> dict[str, Any]:
    """Totaux détectés sur libellés (sous-total, timbre, TTC, paiements, reste dû)."""
    from app.services.invoice_extraction import extract_totals_extended

    return extract_totals_extended(ocr_text)


def validate_financials(
    invoice: dict[str, Any],
    *,
    ocr_text: str = "",
) -> dict[str, Any]:
    """Contrôles simples : somme lignes vs sous-total, TTC vs HT + timbre + TVA."""
    items = invoice.get("items") or []
    line_sum = sum(float(i.get("line_total") or i.get("line_subtotal") or 0) for i in items)
    sub = float(invoice.get("subtotal_htva") or invoice.get("subtotal_amount") or 0)
    ttc = float(invoice.get("total_ttc") or invoice.get("total_amount") or 0)
    tva = float(invoice.get("tax_amount") or 0)
    stamp = float(
        invoice.get("stamp_duty") or invoice.get("stamp_tax") or invoice.get("timbre") or 0
    )
    warnings: list[str] = []
    flags: dict[str, bool] = {}
    expected_ttc = sub + stamp + tva

    tol = max(3.0, line_sum * 0.02) if line_sum else 3.0
    if sub > 0 and line_sum > 0:
        flags["lines_match_subtotal"] = abs(line_sum - sub) <= tol
        if not flags["lines_match_subtotal"]:
            warnings.append("line_sum_vs_subtotal_mismatch")
    else:
        flags["lines_match_subtotal"] = True

    tol_ttc = max(3.0, ttc * 0.02) if ttc else 3.0
    if ttc > 0 and expected_ttc > 0:
        flags["total_consistent"] = abs(ttc - expected_ttc) <= tol_ttc
        if not flags["total_consistent"]:
            warnings.append("ttc_vs_subtotal_stamp_tva")
    else:
        flags["total_consistent"] = True

    if ocr_text and detect_currency(ocr_text) == "TND" and str(invoice.get("currency") or "").upper() == "EUR":
        warnings.append("currency_eur_suspected_tnd_doc")

    paid = float(invoice.get("amount_paid") or 0)
    rem = float(invoice.get("remaining_due") or 0)
    if ttc > 0 and paid > 0 and rem >= 0 and abs(ttc - paid - rem) > tol_ttc:
        warnings.append("paid_plus_remaining_vs_ttc")

    return {
        "warnings": warnings,
        "flags": flags,
        "line_sum": line_sum,
        "expected_ttc": expected_ttc,
    }


def detect_table_region_from_ocr(ocr_text: str) -> tuple[int, int]:
    """Bornes de lignes : après en-tête colonnes type ARTICLE / DESIGNATION jusqu’aux totaux."""
    lines = [ln.rstrip() for ln in (ocr_text or "").splitlines()]
    n = len(lines)
    start_idx, end_idx = 0, n
    first_hdr: int | None = None
    for i, ln in enumerate(lines):
        if _TABLE_START_RE.search(ln or ""):
            first_hdr = i
            break
    if first_hdr is not None:
        start_idx = first_hdr + 1
        for j in range(start_idx, n):
            if _TABLE_END_RE.search(lines[j] or ""):
                end_idx = j
                break
    return start_idx, end_idx


def extract_table_headers(ocr_text: str) -> list[str]:
    """En-tête de colonnes (ligne précédant la zone tableau si présente)."""
    lines = [ln.rstrip() for ln in (ocr_text or "").splitlines()]
    s, _ = detect_table_region_from_ocr(ocr_text)
    if s > 0 and s - 1 < len(lines):
        row = lines[s - 1].strip()
        if row:
            return [p for p in re.split(r"\s{2,}|\t+", row) if p]
    return []


def parse_table_rows(ocr_text: str) -> list[dict[str, Any]]:
    """Alias : lignes détectées comme articles (API stable)."""
    return detect_invoice_table_lines(ocr_text)


def normalize_financial_columns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attache `_normalized` (PU, qté, sous-total) à chaque ligne détectée."""
    out: list[dict[str, Any]] = []
    for r in rows:
        nums = r.get("raw_numbers") or []
        p = parse_line_numbers([float(x) for x in nums])
        row = dict(r)
        row["_normalized"] = p
        out.append(row)
    return out


def validate_table_math(
    rows: list[dict[str, Any]],
    *,
    tol_ratio: float = 0.08,
) -> dict[str, Any]:
    """Vérifie qté × PU ≈ sous-total sur les `_normalized`."""
    ie = _ie()
    bad: list[int] = []
    for i, r in enumerate(rows):
        p = r.get("_normalized") or {}
        if not isinstance(p, dict):
            continue
        q = float(p.get("quantity") or 0)
        pu = float(p.get("unit_price") or 0)
        lt = float(p.get("line_subtotal") or 0)
        if q <= 0 or pu <= 0 or lt <= 0:
            continue
        q2, pu2 = ie._reconcile_qty_unit_line_total(q, pu, lt)
        if abs(q2 * pu2 - lt) > max(2.0, lt * tol_ratio):
            bad.append(i)
    return {"coherent": not bad, "bad_row_indices": bad}
