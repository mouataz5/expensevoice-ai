"""Provider OCR : Microsoft Table Transformer (structure) + PaddleOCR par cellule."""

from __future__ import annotations

from app.schemas.invoice_pipeline import OCRResult
from app.services.ocr.tatr_table_service import extract_document_with_tatr_paddle


class TatrPaddleOcrProvider:
    name = "tatr_paddle"

    def extract(self, image_path: str) -> OCRResult:
        return extract_document_with_tatr_paddle(image_path)
