"""
Validation arithmétique tableau + totaux document (après reconstruction des lignes).
"""
from __future__ import annotations

from typing import Any

from app.schemas.invoice_pipeline import InvoiceLineDraft
from app.services.invoice_facades.table_correction_engine import validate_corrected_table
from app.utils.money import to_float_safe


def _approx(a: float, b: float, *, tol_ratio: float, tol_abs: float) -> bool:
    m = max(abs(a), abs(b), 1.0)
    return abs(a - b) <= max(tol_abs, m * tol_ratio)


def validate_line_items_math(items: list[InvoiceLineDraft]) -> dict[str, Any]:
    """Contrôle qté × PU vs sous-total pour chaque ligne (brouillon API)."""
    bad: list[int] = []
    for i, ln in enumerate(items):
        q = to_float_safe(ln.quantity)
        pu = to_float_safe(ln.unit_price)
        st = to_float_safe(ln.line_subtotal)
        if q and pu and st and st > 0:
            if not _approx(float(q) * float(pu), float(st), tol_ratio=0.03, tol_abs=max(2.0, abs(float(st)) * 0.03)):
                bad.append(i)
    return {
        "line_math_ok": len(bad) == 0,
        "incoherent_row_indices": bad,
        "n_lines": len(items),
    }


def validate_table_models_against_totals(rows: list[Any], totals: dict[str, Any]) -> dict[str, Any]:
    """Enveloppe `validate_corrected_table` pour modèles internes (TableRowModel)."""
    return validate_corrected_table(rows, totals)


__all__ = [
    "validate_line_items_math",
    "validate_table_models_against_totals",
]
