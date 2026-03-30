"""
OCR service abstraction — extract text from invoice images.
Supports Arabic + French (Tunisian invoices).
Priority: pytesseract (Tesseract) → EasyOCR → empty fallback.
Includes image preprocessing for phone photos.
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/heic", "image/heif"}

TESSERACT_LANG_PRIMARY = os.getenv("TESSERACT_LANG", "fra+eng")
TESSERACT_LANG_SECONDARY = "ara+fra+eng"

MIN_GOOD_OCR_LEN = 400


def _preprocess_image(img: "Image.Image") -> list["Image.Image"]:
    """
    Return a list of preprocessed versions of the image for OCR.
    Handles phone photos: low contrast, skewed lighting, small text.
    """
    from PIL import ImageEnhance, ImageFilter

    variants = [img]

    gray = img.convert("L")
    variants.append(gray)

    contrast = ImageEnhance.Contrast(gray).enhance(2.0)
    sharp = contrast.filter(ImageFilter.SHARPEN)
    variants.append(sharp)

    w, h = img.size
    if max(w, h) < 3000:
        scale = 2 if max(w, h) < 2000 else 1.5
        big = img.resize((int(w * scale), int(h * scale)), getattr(img, "LANCZOS", 1))
        gray_big = big.convert("L")
        contrast_big = ImageEnhance.Contrast(gray_big).enhance(2.5)
        sharp_big = contrast_big.filter(ImageFilter.SHARPEN).filter(ImageFilter.SHARPEN)
        variants.append(sharp_big)

        for thresh in (130, 150, 170):
            bw = sharp_big.point(lambda x, t=thresh: 0 if x < t else 255, "1")
            variants.append(bw)

    try:
        import numpy as np
        from PIL import Image as _Img
        source_gray = sharp_big if max(w, h) < 3000 else gray
        arr = np.array(source_gray)
        c_val = 10
        blurred = _Img.fromarray(arr).filter(ImageFilter.GaussianBlur(radius=15))
        mean = np.array(blurred, dtype=np.float64)
        adaptive = ((arr.astype(np.float64) > (mean - c_val)) * 255).astype(np.uint8)
        variants.append(_Img.fromarray(adaptive))
    except (ImportError, NameError):
        pass

    return variants


def _extract_with_tesseract(image_path: str) -> str | None:
    """Try pytesseract with preprocessing and multiple configs. Returns best text."""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        variants = _preprocess_image(img)

        best_text = ""
        for variant in variants:
            for lang, psm in [
                (TESSERACT_LANG_PRIMARY, "6"),
                (TESSERACT_LANG_PRIMARY, "3"),
                (TESSERACT_LANG_PRIMARY, "4"),
                (TESSERACT_LANG_SECONDARY, "6"),
            ]:
                try:
                    text = pytesseract.image_to_string(variant, lang=lang, config=f"--psm {psm}")
                    text = (text or "").strip()
                    if len(text) > len(best_text):
                        best_text = text
                    if len(best_text) > MIN_GOOD_OCR_LEN:
                        break
                except Exception:
                    continue
            if len(best_text) > MIN_GOOD_OCR_LEN:
                break

        if best_text:
            logger.info("Tesseract OCR extracted %d chars from %s", len(best_text), image_path)
            return best_text
        return best_text
    except ImportError:
        logger.debug("pytesseract not installed; skipping Tesseract OCR")
        return None
    except Exception as e:
        logger.warning("Tesseract OCR failed for %s: %s", image_path, e)
        return None


def _extract_with_easyocr(image_path: str) -> str | None:
    """Try EasyOCR. Returns text or None if unavailable."""
    try:
        import easyocr

        reader = easyocr.Reader(
            ["ar", "fr", "en"],
            gpu=os.getenv("EASYOCR_GPU", "false").lower() == "true",
        )
        result = reader.readtext(str(image_path), detail=0, paragraph=True)
        text = "\n".join(result).strip() if result else ""
        if text:
            logger.info("EasyOCR extracted %d chars from %s", len(text), image_path)
            return text
        return text
    except ImportError:
        logger.debug("EasyOCR not installed; skipping")
        return None
    except Exception as e:
        logger.warning("EasyOCR failed for %s: %s", image_path, e)
        return None


def extract_text(image_path: str) -> str:
    """
    Extract text from image. Tries Tesseract first, then EasyOCR.
    Returns raw OCR text or empty string.
    """
    path = Path(image_path)
    if not path.is_file():
        logger.warning("OCR: file not found %s", image_path)
        return ""

    text = _extract_with_tesseract(str(path))
    if text is not None and text:
        return text

    text = _extract_with_easyocr(str(path))
    if text is not None and text:
        return text

    logger.warning("No OCR engine produced text for %s. Install tesseract or easyocr.", image_path)
    return ""
