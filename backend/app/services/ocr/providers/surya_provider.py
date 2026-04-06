"""Provider OCR Surya — délègue à surya_ocr_service."""
from __future__ import annotations

from app.schemas.invoice_pipeline import OCRResult
from app.services.ocr.surya_ocr_service import extract_surya_document


class SuryaOcrProvider:
    name = "surya"

    def extract(self, image_path: str) -> OCRResult:
        return extract_surya_document(image_path)
