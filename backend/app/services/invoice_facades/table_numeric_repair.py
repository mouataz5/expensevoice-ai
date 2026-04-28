"""
Réparation des affectations numériques (QTE / P.U / P.HT / P.TTC) après assignation géométrique.

Règles : qté ≤ 1000 ; P.HT ≈ QTE×P.U ; P.TTC ≥ P.HT si présente.
"""
from __future__ import annotations

from itertools import permutations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.invoice_facades.surya_table_extractor import TableRowModel

_MAX_QTY = 200.0


def _approx(a: float, b: float, *, tol_ratio: float = 0.02, tol_abs: float = 2.0) -> bool:
    m = max(abs(a), abs(b), 1.0)
    return abs(a - b) <= max(tol_abs, m * tol_ratio)


def _qty_plausible(q: float) -> bool:
    return 0 < q <= _MAX_QTY


def _ok_triple(q: float, pu: float, ht: float) -> bool:
    if not _qty_plausible(q) or pu <= 0 or ht <= 0:
        return False
    return _approx(q * pu, ht, tol_ratio=0.02, tol_abs=max(2.0, abs(ht) * 0.02))


def _ok_quad(q: float, pu: float, ht: float, ttc: float) -> bool:
    if not _ok_triple(q, pu, ht):
        return False
    if ttc <= 0:
        return False
    # P.TTC ligne ≥ P.HT (TVA ligne ou arrondi)
    return ttc + 0.01 >= ht * 0.995


def repair_numeric_column_assignment(r: TableRowModel) -> tuple[TableRowModel, str | None]:
    from app.services.invoice_facades.surya_table_extractor import TableRowModel as TRM

    q0 = float(r.quantity) if r.quantity is not None else None
    pu0 = float(r.unit_price) if r.unit_price is not None else None
    ht0 = float(r.line_ht) if r.line_ht is not None else None
    ttc0 = float(r.line_ttc) if r.line_ttc is not None and float(r.line_ttc) > 0 else None

    if q0 is None or pu0 is None or ht0 is None:
        return r, None
    if q0 <= 0 or pu0 <= 0 or ht0 <= 0:
        return r, None

    triple_ok = _qty_plausible(q0) and _ok_triple(q0, pu0, ht0)
    ttc_bad = ttc0 is not None and ttc0 + 0.5 < ht0
    if triple_ok and not ttc_bad:
        return r, None

    if ttc0 is not None and (not triple_ok or ttc_bad):
        best_4: tuple[float, float, float, float] | None = None
        best_err = 1e30
        for a, b, c, d in set(permutations((q0, pu0, ht0, ttc0), 4)):
            if not _ok_quad(a, b, c, d):
                continue
            err = abs(a * b - c)
            pref = max(0.0, a - 99.0) * 0.02
            eff = err + pref
            if eff < best_err:
                best_err = eff
                best_4 = (a, b, c, d)
        if best_4 is not None:
            q, pu, ht, ttc = best_4
            return (
                TRM(
                    description=r.description,
                    unit=r.unit,
                    quantity=round(q) if abs(q - round(q)) < 0.051 else round(q, 4),
                    unit_price=round(pu, 6),
                    line_ht=round(ht, 3),
                    line_ttc=round(ttc, 3),
                    source_row_id=r.source_row_id,
                ),
                "numeric_columns_repaired_perm4",
            )

    if triple_ok:
        return r, None

    best: tuple[float, float, float] | None = None
    best_err = 1e30
    for a, b, c in set(permutations((q0, pu0, ht0), 3)):
        if not _ok_triple(a, b, c):
            continue
        err = abs(a * b - c)
        pref = max(0.0, a - 99.0) * 0.02
        eff = err + pref
        if eff < best_err:
            best_err = eff
            best = (a, b, c)
    if best is None:
        return r, None
    q, pu, ht = best
    return (
        TRM(
            description=r.description,
            unit=r.unit,
            quantity=round(q) if abs(q - round(q)) < 0.051 else round(q, 4),
            unit_price=round(pu, 6),
            line_ht=round(ht, 3),
            line_ttc=r.line_ttc,
            source_row_id=r.source_row_id,
        ),
        "numeric_columns_repaired_perm3",
    )


__all__ = ["repair_numeric_column_assignment", "_MAX_QTY"]
