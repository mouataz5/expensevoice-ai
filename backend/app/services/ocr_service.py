"""
OCR service abstraction — extract text from invoice images.
Supports Arabic + French (Tunisian invoices). Uses EasyOCR when available.
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Max size 8MB
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/heic", "image/heif"}


def extract_text(image_path: str) -> str:
    """
    Extract text from image at image_path. Returns raw OCR text.
    Uses EasyOCR with Arabic + French + English. If not installed, returns empty string.
    """
    path = Path(image_path)
    if not path.is_file():
        logger.warning("OCR: file not found %s", image_path)
        return ""

    try:
        import easyocr
        reader = easyocr.Reader(["ar", "fr", "en"], gpu=os.getenv("EASYOCR_GPU", "false").lower() == "true")
        result = reader.readtext(str(path), detail=0, paragraph=True)
        text = "\n".join(result).strip() if result else ""
        logger.info("OCR extracted %d chars from %s", len(text), image_path)
        return text
    except ImportError:
        logger.warning("EasyOCR not installed. pip install easyocr for invoice OCR.")
        return ""
    except Exception as e:
        logger.exception("OCR failed for %s: %s", image_path, e)
        raise
