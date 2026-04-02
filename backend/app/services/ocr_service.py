"""
OCR — compatibilité `extract_text()` + orchestrateur modulaire (providers).

Utilise `app.services.ocr.run_ocr` (PaddleOCR / Tesseract / EasyOCR selon OCR_PROVIDER).
"""
import logging
from pathlib import Path

from app.services.ocr.ocr_orchestrator import run_ocr

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/heic", "image/heif"}


def extract_text(image_path: str) -> str:
    """
    Extract text from image using le pipeline OCR configuré.
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
