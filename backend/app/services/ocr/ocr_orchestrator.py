"""
Orchestration OCR : OCR_PROVIDER = paddleocr | tesseract | easyocr | auto.
auto : paddleocr puis tesseract puis easyocr (100 % open source, sans cloud OCR).
"""
from __future__ import annotations

import logging
import os

from app.schemas.invoice_pipeline import OCRResult
from app.services.ocr.providers.easyocr_provider import EasyOcrProvider
from app.services.ocr.providers.paddleocr_provider import PaddleOcrProvider
from app.services.ocr.providers.tesseract import TesseractOcrProvider

logger = logging.getLogger(__name__)


def run_ocr(image_path: str) -> OCRResult:
    # Défaut auto = PaddleOCR d'abord puis Tesseract / EasyOCR si texte vide.
    mode = (os.getenv("OCR_PROVIDER") or "auto").strip().lower()
    providers: list = []

    if mode in ("paddle", "paddleocr"):
        providers = [PaddleOcrProvider()]
    elif mode == "tesseract":
        providers = [TesseractOcrProvider()]
    elif mode == "easyocr":
        providers = [EasyOcrProvider()]
    else:
        providers = [
            PaddleOcrProvider(),
            TesseractOcrProvider(),
            EasyOcrProvider(),
        ]

    last: OCRResult | None = None
    for p in providers:
        try:
            res = p.extract(image_path)
            last = res
            if (res.raw_text or "").strip():
                logger.info("OCR provider=%s chars=%d", p.name, len(res.raw_text))
                return res
        except Exception as e:
            logger.warning("OCR provider %s error: %s", getattr(p, "name", p), e)
            last = OCRResult(raw_text="", metadata={"error": str(e)[:200]})

    return last or OCRResult(raw_text="", metadata={"error": "no_provider"})
