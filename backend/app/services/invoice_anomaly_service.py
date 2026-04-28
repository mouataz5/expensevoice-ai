"""
Business anomaly detection for invoice outputs.

Goal: prefer "no trusted output" over wrong financial data.
"""
from __future__ import annotations

from typing import Any


def _to_float(v: Any) -> float | None:
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def detect_invoice_anomalies(extracted: dict[str, Any]) -> list[str]:
    """
    Lightweight anomaly checks used for API warnings/insights.
    """
    warnings: list[str] = []

    items = list((extracted or {}).get("items") or [])
    totals = dict((extracted or {}).get("totals") or {})

    # Line-level checks
    computed_sum = 0.0
    n_valid_lines = 0
    for idx, row in enumerate(items):
        q = _to_float(row.get("quantity"))
        pu = _to_float(row.get("unit_price"))
        lt = _to_float(row.get("line_total") or row.get("line_subtotal"))

        if q is not None:
            if q <= 0:
                warnings.append(f"Ligne {idx + 1}: quantité nulle/négative")
            elif q > 200:
                warnings.append(f"Ligne {idx + 1}: quantité anormalement élevée ({q:g})")

        if pu is not None and pu <= 0:
            warnings.append(f"Ligne {idx + 1}: prix unitaire nul/négatif")

        if q is not None and pu is not None and lt is not None and lt > 0:
            exp = q * pu
            tol = max(2.0, abs(lt) * 0.04)
            if abs(exp - lt) > tol:
                warnings.append(f"Ligne {idx + 1}: incohérence qté × PU vs total ligne")

        if lt is not None and lt > 0:
            computed_sum += lt
            n_valid_lines += 1

    # Document-level checks
    subtotal = _to_float(totals.get("htva"))
    tax = _to_float(totals.get("tva")) or 0.0
    stamp = _to_float(totals.get("timbre")) or 0.0
    total = _to_float(totals.get("ttc"))

    if subtotal is not None and n_valid_lines > 0:
        tol = max(3.0, abs(subtotal) * 0.05)
        if abs(computed_sum - subtotal) > tol:
            warnings.append("Incohérence entre somme des lignes et sous-total HT")

    if subtotal is not None and total is not None:
        expected_ttc = subtotal + tax + stamp
        tol = max(3.0, abs(total) * 0.04)
        if abs(expected_ttc - total) > tol:
            warnings.append("Incohérence formule total TTC (HT + TVA + timbre)")

    # Remove duplicates while preserving order
    out: list[str] = []
    seen: set[str] = set()
    for w in warnings:
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out


__all__ = ["detect_invoice_anomalies"]

