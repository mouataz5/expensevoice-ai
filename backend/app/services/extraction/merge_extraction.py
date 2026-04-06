"""
Fusion brouillon LLM + heuristique — réutilise la logique `invoice_draft_merge`.
"""
from __future__ import annotations

from app.services.invoice_draft_merge import (
    merge_draft_with_heuristic,
    merge_llm_and_heuristic_document,
    merge_llm_and_heuristic_invoice,
)

__all__ = [
    "merge_draft_with_heuristic",
    "merge_llm_and_heuristic_invoice",
    "merge_llm_and_heuristic_document",
]
