"""Provider OCR Paddle PP-StructureV3 (layout + tables) avec repli PaddleOCR classique."""
from __future__ import annotations

import logging

from app.schemas.invoice_pipeline import OCRResult
from app.services.ocr.paddle_ocr_service import extract_text_from_image
from app.services.ocr.paddle_structure_service import (
    extract_document_with_pp_structure,
    is_paddle_structure_supported,
)

logger = logging.getLogger(__name__)


class PaddleStructureOcrProvider:
    name = "paddle_structure"

    def extract(self, image_path: str) -> OCRResult:
        if not is_paddle_structure_supported():
            logger.warning("paddlex[ocr] ou PP-Structure indisponible — repli paddleocr")
            return extract_text_from_image(image_path)
        try:
            res = extract_document_with_pp_structure(image_path)
            if (res.raw_text or "").strip():
                return res
            if res.metadata.get("structured_tables"):
                return res
        except Exception as e:
            logger.warning("PaddleStructureOcrProvider: %s — repli paddleocr", e)
        return extract_text_from_image(image_path)
