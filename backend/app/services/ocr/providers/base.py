from __future__ import annotations

from typing import Protocol

from app.schemas.invoice_pipeline import OCRResult


class OcrProvider(Protocol):
    name: str

    def extract(self, image_path: str) -> OCRResult:
        ...
