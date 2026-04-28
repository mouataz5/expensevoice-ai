"""Couche vision multimodale (LLaVA / Ollama) — validation auxiliaire, sans remplacer l’OCR."""

from app.services.vision.document_visual_validator import (
    apply_llava_merge_to_pipeline_state,
    maybe_apply_ollama_llava_after_validation,
    should_run_llava_visual_validation,
)
from app.services.vision.ollama_llava_service import (
    assess_manual_review_need,
    classify_document_type,
    is_ollama_vision_enabled,
    run_combined_visual_audit,
    validate_header_blocks,
    validate_totals_block,
)

__all__ = [
    "apply_llava_merge_to_pipeline_state",
    "assess_manual_review_need",
    "classify_document_type",
    "is_ollama_vision_enabled",
    "maybe_apply_ollama_llava_after_validation",
    "run_combined_visual_audit",
    "should_run_llava_visual_validation",
    "validate_header_blocks",
    "validate_totals_block",
]
