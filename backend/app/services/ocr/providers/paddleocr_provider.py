"""Provider OCR PaddleOCR — délègue à paddle_ocr_service."""
from __future__ import annotations

from app.schemas.invoice_pipeline import OCRResult
from app.services.ocr.paddle_ocr_service import extract_text_from_image


class PaddleOcrProvider:
    name = "paddleocr"

    def extract(self, image_path: str) -> OCRResult:
        return extract_text_from_image(image_path)
