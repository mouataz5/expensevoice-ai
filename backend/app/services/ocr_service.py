"""
OCR — compatibility `extract_text()` + modular orchestrator (providers).

Uses `app.services.ocr.run_ocr` (PaddleOCR / Tesseract / EasyOCR per OCR_PROVIDER).
"""
import logging
from pathlib import Path

from app.services.ocr.ocr_orchestrator import run_ocr

logger = logging.getLogger(__name__)

# Mime/size validation for upload API (app.api.invoices)
ALLOWED_MIME = {"image/jpeg", "image/png", "image/heic", "image/heif", "image/webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB


def extract_text(image_path: str) -> str:
    """
    Extract text from image using the configured OCR pipeline.
    Returns raw OCR text or empty string.
    """
    path = Path(image_path)
    if not path.is_file():
        logger.warning("OCR: file not found %s", image_path)
        return ""

    res = run_ocr(str(path))
    text = (res.raw_text or "").strip()
    if text:
        logger.info("OCR extracted %d chars from %s", len(text), image_path)
    else:
        logger.warning("No OCR text for %s (metadata=%s)", image_path, res.metadata)
    return text
