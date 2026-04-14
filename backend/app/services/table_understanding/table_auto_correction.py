"""
Auto-correction des assignations numériques par permutations / score (document-aware).

Délègue au moteur existant `table_correction_engine` pour éviter deux logiques divergentes.
"""
from __future__ import annotations

from typing import Any

from app.services.invoice_facades.table_correction_engine import (
    generate_candidate_assignments,
    repair_row_assignment,
    score_assignment,
)


def score_candidate_assignment(
    row: Any,
    assignment: dict[str, float | None],
    document_context: dict[str, Any],
) -> tuple[float, dict[str, float]]:
    """Score 0..1 + détails pour un candidat (qty, pu, line_ht, line_ttc)."""
    return score_assignment(row, assignment, document_context)


def auto_correct_row(row: Any, document_context: dict[str, Any]) -> dict[str, Any]:
    """Alias explicite vers `repair_row_assignment`."""
    return repair_row_assignment(row, document_context)


def auto_correct_table(rows: list[Any], document_context: dict[str, Any]) -> list[dict[str, Any]]:
    """Corrige chaque ligne ; retourne la liste des journaux de correction."""
    return [repair_row_assignment(r, document_context) for r in rows]


__all__ = [
    "auto_correct_row",
    "auto_correct_table",
    "generate_candidate_assignments",
    "score_candidate_assignment",
]
