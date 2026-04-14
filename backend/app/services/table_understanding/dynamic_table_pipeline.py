"""
Orchestration du flux « table understanding » : structure → inférence → correction → validation → revue.

S'appuie sur Surya TableRec + moteurs existants (`surya_table_extractor`, `table_correction_engine`).
Contrat stable pour extension PP-Structure derrière `table_structure_service`.
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.invoice_pipeline import InvoiceLineDraft, OCRResult
from app.services.invoice_facades.surya_table_extractor import extract_invoice_lines_from_surya_metadata
from app.services.ocr.cell_ocr_service import cells_from_table_dict
from app.services.ocr.table_structure_service import (
    extract_table_structures_from_ocr_metadata,
    pick_largest_table,
)
from app.services.validation.review_decision import decide_table_extraction_review

logger = logging.getLogger(__name__)


def run_dynamic_table_understanding(
    ocr: OCRResult,
    document_hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Extrait les lignes articles depuis la grille structurée avec garde-fous qualité.

    Retourne:
      - lines: lignes **approuvées** pour alimenter le brouillon (vide si confiance basse).
      - candidate_lines: même jeu avant filtre « low » (debug / audit).
      - review: extraction_status, manual_review_required, confidence_global, reasons
      - structure_debug: aperçu structures / cellules normalisées
      - surya_debug: blob historique `extract_invoice_lines_from_surya_metadata`
    """
    structure_debug: dict[str, Any] = {
        "structures_found": 0,
        "largest_table_cells": 0,
        "normalized_cell_sample": [],
    }

    meta = dict(ocr.metadata or {})
    structures = extract_table_structures_from_ocr_metadata(meta)
    structure_debug["structures_found"] = len(structures)
    largest = pick_largest_table(structures)
    if largest and largest.cells:
        structure_debug["largest_table_cells"] = len(largest.cells)
        tbl_dict = {
            "cells": cells_from_table_dict(
                {"cells": largest.cells, "table_idx": largest.table_idx, "page": largest.page}
            ),
            "table_idx": largest.table_idx,
            "page": largest.page,
        }
        structure_debug["normalized_cell_sample"] = tbl_dict["cells"][:12]

    candidate_lines, surya_dbg = extract_invoice_lines_from_surya_metadata(
        meta,
        document_hints=document_hints,
    )

    tc = dict(surya_dbg.get("table_correction") or {})
    table_validation = dict(tc.get("global_validation") or {})
    manual = bool(tc.get("manual_review_required"))
    engine_rows = list(tc.get("rows") or [])
    confs = [float(r.get("confidence") or 0.0) for r in engine_rows]
    mean_c = sum(confs) / len(confs) if confs else None

    review = decide_table_extraction_review(
        n_lines=len(candidate_lines),
        table_validation=table_validation,
        manual_review_flag=manual,
        mean_row_confidence=mean_c,
    )

    trusted: list[InvoiceLineDraft] = list(candidate_lines)
    if review["extraction_status"] == "low":
        trusted = []
        surya_dbg = dict(surya_dbg)
        surya_dbg["applied_to_draft"] = False
        surya_dbg["reason"] = "dynamic_table_low_confidence"
        logger.info(
            "dynamic_table_pipeline: rejected %d candidate lines (status=low, reasons=%s)",
            len(candidate_lines),
            review.get("reasons"),
        )

    surya_dbg = dict(surya_dbg)
    surya_dbg["dynamic_table_review"] = review
    surya_dbg["dynamic_table_structure"] = structure_debug

    return {
        "lines": trusted,
        "candidate_lines": candidate_lines,
        "review": review,
        "structure_debug": structure_debug,
        "surya_debug": surya_dbg,
    }


__all__ = ["run_dynamic_table_understanding"]
