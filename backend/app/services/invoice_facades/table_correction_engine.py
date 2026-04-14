"""
Moteur de correction tabulaire post-extraction.

Objectif: améliorer la cohérence des lignes articles sans modifier les endpoints.
"""
from __future__ import annotations

import itertools
import os
from typing import Any


def _to_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        x = float(v)
        if x != x:  # NaN
            return None
        return x
    except (TypeError, ValueError):
        return None


def _approx(a: float | None, b: float | None, *, tol_ratio: float = 0.02, tol_abs: float = 2.0) -> bool:
    if a is None or b is None:
        return False
    m = max(abs(a), abs(b), 1.0)
    return abs(a - b) <= max(tol_abs, m * tol_ratio)


def _row_to_map(row: Any) -> dict[str, float | None]:
    return {
        "quantity": _to_float(row.quantity),
        "unit_price": _to_float(row.unit_price),
        "line_ht": _to_float(row.line_ht),
        "line_ttc": _to_float(row.line_ttc),
    }


def generate_candidate_assignments(row: Any) -> list[dict[str, float | None]]:
    """
    Génère des mappings candidats quantity/unit_price/line_ht/line_ttc.
    On utilise les valeurs numériques déjà extraites et on teste des permutations plausibles.
    """
    base = _row_to_map(row)
    vals = [v for v in base.values() if v is not None and v > 0]
    if not vals:
        return [base]

    # Candidat 1: mapping actuel (prior géométrique implicite)
    out: list[dict[str, float | None]] = [dict(base)]
    keys = ("quantity", "unit_price", "line_ht", "line_ttc")

    # Permutations limitées pour stabilité/perf.
    uniq = sorted(set(round(v, 6) for v in vals))
    for perm in itertools.permutations(uniq, min(len(uniq), 4)):
        cand: dict[str, float | None] = {k: None for k in keys}
        for i, p in enumerate(perm):
            cand[keys[i]] = float(p)
        out.append(cand)

    # Dédoublonnage
    seen: set[tuple[Any, ...]] = set()
    dedup: list[dict[str, float | None]] = []
    for c in out:
        sig = (c.get("quantity"), c.get("unit_price"), c.get("line_ht"), c.get("line_ttc"))
        if sig in seen:
            continue
        seen.add(sig)
        dedup.append(c)
    return dedup[:40]


def _tax_rate_from_context(document_context: dict[str, Any]) -> float | None:
    totals = document_context.get("totals") or {}
    return _to_float(document_context.get("tax_rate_percent")) or _to_float(
        totals.get("tax_rate_percent")
    )


def score_assignment(
    row: Any,
    assignment: dict[str, float | None],
    document_context: dict[str, Any],
) -> tuple[float, dict[str, float]]:
    """
    Score 0..1 avec pondérations:
    - math 35%, ligne TVA (HT→TTC) 10%, geometry 18%, type 12%, cross-row 13%, totals 12%.
    """
    q = _to_float(assignment.get("quantity"))
    pu = _to_float(assignment.get("unit_price"))
    ht = _to_float(assignment.get("line_ht"))
    ttc = _to_float(assignment.get("line_ttc"))
    tax_r = _tax_rate_from_context(document_context)

    # 1) cohérence math
    math_s = 0.0
    if q and pu and ht:
        exp = q * pu
        if _approx(exp, ht, tol_ratio=0.02, tol_abs=max(2.0, abs(ht) * 0.02)):
            math_s = 1.0
        elif _approx(exp, ht, tol_ratio=0.06, tol_abs=8.0):
            math_s = 0.6
    elif q and pu and not ht:
        math_s = 0.45

    # 1b) cohérence HT → TTC (taux document, ex. devis TN 19 %)
    line_tax_s = 0.5
    if tax_r is not None and tax_r > 0 and ht and ttc:
        exp_ttc = ht * (1.0 + tax_r / 100.0)
        if _approx(ttc, exp_ttc, tol_ratio=0.002, tol_abs=max(1.0, abs(ttc) * 0.002)):
            line_tax_s = 1.0
        else:
            line_tax_s = 0.12
    elif tax_r is not None and tax_r > 0 and (ht is None or ttc is None):
        line_tax_s = 0.55

    # 2) prior géométrique (mapping existant)
    base = _row_to_map(row)
    geom_s = 0.0
    equal_slots = 0
    considered = 0
    for k in ("quantity", "unit_price", "line_ht", "line_ttc"):
        bv = base.get(k)
        av = assignment.get(k)
        if bv is None or av is None:
            continue
        considered += 1
        if _approx(float(bv), float(av), tol_ratio=0.0, tol_abs=0.0001):
            equal_slots += 1
    if considered:
        geom_s = equal_slots / considered
    else:
        geom_s = 0.5

    # 3) plausibilité type
    type_s = 0.0
    if q is not None and q > 0:
        q_intish = abs(q - round(q)) < 0.05
        q_reasonable = q <= 10000
        type_s += 0.5 if (q_intish and q_reasonable) else 0.2
    if pu is not None and pu > 0:
        type_s += 0.3 if pu <= 1_000_000 else 0.05
    if ht is not None and ht > 0:
        type_s += 0.2
    type_s = min(1.0, type_s)

    # 4) cohérence inter-lignes
    row_stats = document_context.get("row_stats") or {}
    med_q = _to_float(row_stats.get("median_quantity"))
    med_pu = _to_float(row_stats.get("median_unit_price"))
    cross_s = 0.5
    if q and med_q and med_q > 0:
        ratio = max(q, med_q) / min(q, med_q)
        cross_s = 1.0 if ratio <= 3.0 else (0.6 if ratio <= 10.0 else 0.25)
    if pu and med_pu and med_pu > 0:
        ratio = max(pu, med_pu) / min(pu, med_pu)
        cross_s = min(cross_s, 1.0 if ratio <= 4.0 else (0.65 if ratio <= 12.0 else 0.25))

    # 5) cohérence avec totaux doc
    totals = document_context.get("totals") or {}
    sub = _to_float(totals.get("subtotal_amount") or totals.get("subtotal_htva"))
    ttc_doc = _to_float(totals.get("total_amount") or totals.get("total_ttc"))
    total_s = 0.5
    if ht and sub and sub > 0:
        total_s = 0.9 if ht <= sub * 1.2 else 0.2
    if ttc and ht:
        total_s = min(total_s, 1.0 if ttc >= ht else 0.1)
    elif ttc_doc and ht:
        total_s = min(total_s, 0.8 if ht <= ttc_doc * 1.2 else 0.2)

    score = (
        0.35 * math_s
        + 0.10 * line_tax_s
        + 0.18 * geom_s
        + 0.12 * type_s
        + 0.13 * cross_s
        + 0.12 * total_s
    )
    details = {
        "math": round(math_s, 4),
        "line_tax": round(line_tax_s, 4),
        "geometry": round(geom_s, 4),
        "type": round(type_s, 4),
        "cross_row": round(cross_s, 4),
        "totals": round(total_s, 4),
    }
    return float(round(score, 6)), details


def repair_row_assignment(
    row: Any,
    document_context: dict[str, Any],
) -> dict[str, Any]:
    """
    Corrige une ligne si le meilleur candidat est suffisamment fiable.
    """
    min_score = float(os.getenv("TABLE_CORRECTION_MIN_SCORE", "0.72"))
    min_gap = float(os.getenv("TABLE_CORRECTION_MIN_GAP", "0.12"))
    cands = generate_candidate_assignments(row)
    ranked: list[tuple[float, dict[str, float], dict[str, float | None]]] = []
    for c in cands:
        s, d = score_assignment(row, c, document_context)
        ranked.append((s, d, c))
    ranked.sort(key=lambda x: x[0], reverse=True)
    best_s, best_d, best_c = ranked[0]
    second_s = ranked[1][0] if len(ranked) > 1 else 0.0
    can_repair = best_s >= min_score and (best_s - second_s) >= min_gap

    if can_repair:
        # Avoid hard dependency on TableRowModel class to prevent import cycles.
        repaired = row.__class__(
            description=getattr(row, "description", None),
            unit=getattr(row, "unit", None),
            quantity=best_c.get("quantity"),
            unit_price=best_c.get("unit_price"),
            line_ht=best_c.get("line_ht"),
            line_ttc=best_c.get("line_ttc"),
            source_row_id=getattr(row, "source_row_id", None),
        )
    else:
        repaired = row

    return {
        "row": repaired,
        "confidence": float(round(best_s, 4)),
        "second_best": float(round(second_s, 4)),
        "score_gap": float(round(best_s - second_s, 4)),
        "auto_repaired": bool(can_repair),
        "score_details": best_d,
    }


def validate_corrected_table(rows: list[Any], totals: dict[str, Any]) -> dict[str, Any]:
    sum_ht = sum(float(r.line_ht or 0) for r in rows if _to_float(r.line_ht) is not None)
    sum_ttc = sum(float(r.line_ttc or 0) for r in rows if _to_float(r.line_ttc) is not None)
    sub = _to_float(totals.get("subtotal_amount") or totals.get("subtotal_htva"))
    ttc = _to_float(totals.get("total_amount") or totals.get("total_ttc"))
    tva = _to_float(totals.get("tax_amount")) or 0.0
    stamp = _to_float(totals.get("stamp_tax") or totals.get("stamp_duty")) or 0.0

    line_math_ok = True
    incoherent_rows = 0
    for r in rows:
        q = _to_float(r.quantity)
        pu = _to_float(r.unit_price)
        ht = _to_float(r.line_ht)
        ttc_row = _to_float(r.line_ttc)
        if q and pu and ht:
            if not _approx(q * pu, ht, tol_ratio=0.02, tol_abs=max(2.0, abs(ht) * 0.02)):
                line_math_ok = False
                incoherent_rows += 1
        if ttc_row is not None and ht is not None and ttc_row < ht:
            line_math_ok = False
            incoherent_rows += 1

    subtotal_ok = True
    if sub is not None and sum_ht > 0:
        subtotal_ok = _approx(sum_ht, sub, tol_ratio=0.04, tol_abs=max(5.0, abs(sub) * 0.04))

    total_formula_ok = True
    if ttc is not None and (sub is not None):
        total_formula_ok = _approx((sub + tva + stamp), ttc, tol_ratio=0.04, tol_abs=max(6.0, abs(ttc) * 0.04))

    tax_rate_row = _to_float(totals.get("tax_rate_percent"))
    line_tax_ok = True
    if tax_rate_row is not None and tax_rate_row > 0:
        checked = 0
        bad = 0
        for r in rows:
            ht_r = _to_float(r.line_ht)
            ttc_r = _to_float(r.line_ttc)
            if ht_r and ttc_r:
                checked += 1
                exp = ht_r * (1.0 + tax_rate_row / 100.0)
                if not _approx(
                    ttc_r,
                    exp,
                    tol_ratio=0.002,
                    tol_abs=max(1.0, abs(ttc_r) * 0.002),
                ):
                    bad += 1
        if checked > 0:
            line_tax_ok = bad == 0

    global_ok = line_math_ok and subtotal_ok and total_formula_ok and line_tax_ok
    return {
        "line_math_ok": line_math_ok,
        "subtotal_ok": subtotal_ok,
        "total_formula_ok": total_formula_ok,
        "line_tax_ok": line_tax_ok,
        "global_ok": global_ok,
        "sum_ht": round(sum_ht, 3),
        "sum_ttc": round(sum_ttc, 3),
        "incoherent_rows": incoherent_rows,
    }


def decide_manual_review(
    rows: list[dict[str, Any]],
    table_validation: dict[str, Any],
) -> bool:
    if not rows:
        return True
    low_conf = sum(1 for r in rows if float(r.get("confidence") or 0) < 0.6)
    unrepaired = sum(1 for r in rows if not bool(r.get("auto_repaired")))
    if table_validation.get("global_ok") is False:
        return True
    if low_conf >= max(1, len(rows) // 2):
        return True
    if unrepaired >= max(2, len(rows) // 2 + 1):
        return True
    return False

