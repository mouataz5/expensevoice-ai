"""Provider EasyOCR (optionnel)."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from app.schemas.invoice_pipeline import OCRLineSpan, OCRResult

logger = logging.getLogger(__name__)


class EasyOcrProvider:
    name = "easyocr"

    def extract(self, image_path: str) -> OCRResult:
        t0 = time.perf_counter()
        path = Path(image_path)
        if not path.is_file():
            return OCRResult(raw_text="", metadata={"provider": self.name, "error": "file_not_found"})
        try:
            import easyocr
        except ImportError:
            return OCRResult(raw_text="", metadata={"provider": self.name, "error": "import"})

        reader = easyocr.Reader(
            ["ar", "fr", "en"],
            gpu=os.getenv("EASYOCR_GPU", "false").lower() == "true",
        )
        result = reader.readtext(str(path), detail=0, paragraph=True)
        text = "\n".join(result).strip() if result else ""
        lines_out = [OCRLineSpan(text=ln.strip()) for ln in text.splitlines() if ln.strip()]
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return OCRResult(
            raw_text=text,
            lines=lines_out,
            words=[],
            confidence=None,
            metadata={"provider": self.name, "latency_ms": elapsed_ms},
        )
