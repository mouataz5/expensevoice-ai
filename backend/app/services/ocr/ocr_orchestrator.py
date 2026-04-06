"""
Orchestration OCR : OCR_PROVIDER = paddleocr | tesseract | easyocr | surya | auto | liste séparée par virgules.

- auto : paddleocr puis tesseract puis easyocr (comportement historique, sans Surya).
- surya ou surya,paddleocr,tesseract : chaîne explicite (fallback si Surya échoue ou renvoie vide).

Robustesse : nouvelles tentatives par provider (OCR_PROVIDER_ATTEMPTS) et passages
chaîne complets (OCR_CHAIN_ROUNDS) si le texte reste vide.
"""
from __future__ import annotations

import logging
import os
import time

from app.core.pipeline_observability import pipeline_stage
from app.schemas.invoice_pipeline import OCRResult
from app.services.ocr.providers.easyocr_provider import EasyOcrProvider
from app.services.ocr.providers.paddleocr_provider import PaddleOcrProvider
from app.services.ocr.providers.surya_provider import SuryaOcrProvider
from app.services.ocr.providers.tesseract import TesseractOcrProvider
from app.services.ocr.surya_ocr_service import is_surya_available

logger = logging.getLogger(__name__)

_PROVIDER_BUILDERS: dict[str, type] = {
    "paddle": PaddleOcrProvider,
    "paddleocr": PaddleOcrProvider,
    "tesseract": TesseractOcrProvider,
    "easyocr": EasyOcrProvider,
    "surya": SuryaOcrProvider,
}


def _providers_from_csv(mode: str) -> list:
    parts = [p.strip().lower() for p in mode.split(",") if p.strip()]
    out: list = []
    for token in parts:
        cls = _PROVIDER_BUILDERS.get(token)
        if not cls:
            logger.warning("OCR_PROVIDER token inconnu ignoré: %s", token)
            continue
        if token == "surya" and not is_surya_available():
            logger.warning("Surya demandé mais surya-ocr non disponible — entrée ignorée")
            continue
        out.append(cls())
    return out


def _provider_chain() -> list:
    mode = (os.getenv("OCR_PROVIDER") or "auto").strip().lower()
    if "," in mode:
        chain = _providers_from_csv(mode)
        return chain if chain else [PaddleOcrProvider(), TesseractOcrProvider(), EasyOcrProvider()]
    if mode in ("paddle", "paddleocr"):
        return [PaddleOcrProvider()]
    if mode == "tesseract":
        return [TesseractOcrProvider()]
    if mode == "easyocr":
        return [EasyOcrProvider()]
    if mode == "surya":
        if is_surya_available():
            return [SuryaOcrProvider()]
        logger.warning("OCR_PROVIDER=surya mais surya-ocr absent — repli sur auto Paddle/Tesseract/EasyOCR")
        return [
            PaddleOcrProvider(),
            TesseractOcrProvider(),
            EasyOcrProvider(),
        ]
    return [
        PaddleOcrProvider(),
        TesseractOcrProvider(),
        EasyOcrProvider(),
    ]


def _extract_once(p, image_path: str) -> OCRResult:
    """Une tentative d’extraction ; lève si le provider lève."""
    t0 = time.perf_counter()
    res = p.extract(image_path)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    logger.info(
        "ocr_provider_timing",
        extra={
            "pipeline_stage": "ocr_provider",
            "component": "ocr",
            "ocr_provider": getattr(p, "name", str(p)),
            "duration_ms": elapsed_ms,
            "chars": len(res.raw_text or ""),
        },
    )
    return res


def _extract_with_retries(p, image_path: str) -> OCRResult:
    attempts = max(1, int(os.getenv("OCR_PROVIDER_ATTEMPTS", "2")))
    last: OCRResult | None = None
    last_err: Exception | None = None
    for attempt in range(attempts):
        try:
            return _extract_once(p, image_path)
        except Exception as e:
            last_err = e
            logger.warning(
                "OCR provider=%s attempt %d/%d error: %s",
                getattr(p, "name", p),
                attempt + 1,
                attempts,
                e,
            )
            last = OCRResult(
                raw_text="",
                metadata={"error": str(e)[:200], "provider": getattr(p, "name", "?")},
            )
    if last_err:
        logger.warning("OCR provider %s exhausted retries", getattr(p, "name", p))
    return last or OCRResult(raw_text="", metadata={"error": "no_result"})


def run_ocr(image_path: str) -> OCRResult:
    providers = _provider_chain()
    chain_rounds = max(1, int(os.getenv("OCR_CHAIN_ROUNDS", "1")))
    last: OCRResult | None = None

    for round_idx in range(chain_rounds):
        with pipeline_stage(
            "ocr_chain",
            component="ocr",
            extra={"round": round_idx + 1, "chain_rounds": chain_rounds},
        ):
            for p in providers:
                try:
                    res = _extract_with_retries(p, image_path)
                    last = res
                    if (res.raw_text or "").strip():
                        logger.info(
                            "OCR provider=%s chars=%d round=%d",
                            p.name,
                            len(res.raw_text),
                            round_idx + 1,
                        )
                        return res
                except Exception as e:
                    logger.warning("OCR provider %s error: %s", getattr(p, "name", p), e)
                    last = OCRResult(raw_text="", metadata={"error": str(e)[:200]})

        if round_idx + 1 < chain_rounds:
            logger.info("OCR chain round %d empty text, retrying chain", round_idx + 1)

    return last or OCRResult(raw_text="", metadata={"error": "no_provider"})
