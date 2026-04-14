"""
Décision de confiance / reprise manuelle : préférer l'absence de lignes à des lignes non fiables.
"""
from __future__ import annotations

from typing import Any


def decide_table_extraction_review(
    *,
    n_lines: int,
    table_validation: dict[str, Any],
    manual_review_flag: bool,
    mean_row_confidence: float | None = None,
) -> dict[str, Any]:
    """
    Retourne extraction_status (high | medium | low), manual_review_required, reasons.

    - high : tableau cohérent avec totaux et peu ou pas de lignes incohérentes.
    - medium : lignes utilisables avec avertissements (révision UI recommandée).
    - low : ne pas faire confiance aux lignes détaillées ; reprise manuelle.
    """
    reasons: list[str] = []
    inc = int(table_validation.get("incoherent_rows") or 0)
    global_ok = bool(table_validation.get("global_ok"))
    line_ok = bool(table_validation.get("line_math_ok"))
    sub_ok = bool(table_validation.get("subtotal_ok"))
    ttc_ok = bool(table_validation.get("total_formula_ok"))

    if n_lines == 0:
        return {
            "extraction_status": "low",
            "manual_review_required": True,
            "confidence_global": 0.0,
            "reasons": ["no_line_items_from_table"],
        }

    if manual_review_flag:
        reasons.append("table_correction_engine_flagged_review")

    if inc > 0:
        reasons.append(f"incoherent_rows:{inc}")

    if not line_ok:
        reasons.append("line_math_failed")

    if not sub_ok:
        reasons.append("sum_lines_vs_subtotal_mismatch")

    if not ttc_ok:
        reasons.append("ht_tva_vs_ttc_mismatch")

    mrc = mean_row_confidence
    if mrc is not None and mrc < 0.55:
        reasons.append("low_mean_row_confidence")

    # Classification
    if global_ok and inc == 0 and not manual_review_flag:
        status = "high"
        manual = False
        conf = 0.88
    elif global_ok and inc <= max(1, n_lines // 10) and (mrc is None or mrc >= 0.5):
        status = "medium"
        manual = manual_review_flag or inc > 0 or not ttc_ok
        conf = 0.62
    else:
        status = "low"
        manual = True
        conf = 0.28

    return {
        "extraction_status": status,
        "manual_review_required": manual,
        "confidence_global": conf,
        "reasons": reasons or (["ok"] if status == "high" else ["quality_gate"]),
    }


__all__ = ["decide_table_extraction_review"]
