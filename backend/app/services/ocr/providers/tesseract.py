"""Provider OCR Tesseract."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from app.schemas.invoice_pipeline import OCRLineSpan, OCRResult, OCRWordSpan
from app.services.image_preprocessing import exif_transpose, preprocess_variants

logger = logging.getLogger(__name__)

TESSERACT_LANG_PRIMARY = os.getenv("TESSERACT_LANG", "fra+eng")
TESSERACT_LANG_SECONDARY = "ara+fra+eng"


def _ocr_quality_score(text: str) -> int:
    if not (text and str(text).strip()):
        return 0
    t = text.upper()
    score = len(text) // 6
    for kw in (
        "FACTURE",
        "BON DE",
        "TVA",
        "TND",
        "TOTAL",
        "NET ",
        "CLIENT",
        "FOURNISSEUR",
        "TIMBRE",
    ):
        if kw in t:
            score += 28
    score += sum(1 for c in text if c.isdigit()) * 2
    return score


class TesseractOcrProvider:
    name = "tesseract"

    def extract(self, image_path: str) -> OCRResult:
        t0 = time.perf_counter()
        path = Path(image_path)
        if not path.is_file():
            return OCRResult(raw_text="", metadata={"provider": self.name, "error": "file_not_found"})

        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            logger.debug("pytesseract/Pillow missing")
            return OCRResult(raw_text="", metadata={"provider": self.name, "error": "import"})

        img = Image.open(str(path))
        img = exif_transpose(img)
        oriented: list = [img]
        try:
            for rot in (90, 270, 180):
                oriented.append(img.rotate(rot, expand=True))
        except Exception:
            pass

        best_text = ""
        best_score = -1
        for base in oriented:
            for variant in preprocess_variants(base):
                for lang, psm in [
                    (TESSERACT_LANG_PRIMARY, "6"),
                    (TESSERACT_LANG_PRIMARY, "11"),
                    (TESSERACT_LANG_SECONDARY, "6"),
                ]:
                    try:
                        text = pytesseract.image_to_string(
                            variant, lang=lang, config=f"--psm {psm}"
                        )
                        text = (text or "").strip()
                        sc = _ocr_quality_score(text)
                        if sc > best_score or (sc == best_score and len(text) > len(best_text)):
                            best_score = sc
                            best_text = text
                        if best_score >= 520 and len(best_text) >= 220:
                            break
                    except Exception:
                        continue
                if best_score >= 520 and len(best_text) >= 220:
                    break
            if best_score >= 520 and len(best_text) >= 220:
                break

        lines_out = [OCRLineSpan(text=ln.strip()) for ln in best_text.splitlines() if ln.strip()]
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return OCRResult(
            raw_text=best_text,
            lines=lines_out,
            words=[],
            confidence=None,
            metadata={"provider": self.name, "latency_ms": elapsed_ms, "quality_score": best_score},
        )
