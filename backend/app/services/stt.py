"""
STT service — singleton Whisper model, fast config (turbo/large-v3, int8, ar).
Part 1: Speed optimization; model loads once; response time logging.
"""
import logging
import os
import time
from functools import lru_cache

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# Part 1: Faster defaults — turbo or large-v3, int8, device auto, language ar
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "turbo")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "ar")


def _resolve_device() -> str:
    if WHISPER_DEVICE != "auto":
        return WHISPER_DEVICE
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


@lru_cache(maxsize=1)
def get_whisper_model() -> WhisperModel:
    """Load Whisper once per process (singleton)."""
    device = _resolve_device()
    logger.info("Loading Whisper model: model=%s device=%s compute_type=%s", WHISPER_MODEL, device, WHISPER_COMPUTE_TYPE)
    return WhisperModel(WHISPER_MODEL, device=device, compute_type=WHISPER_COMPUTE_TYPE)


def transcribe_audio(
    file_path: str,
    language: str | None = None,
) -> tuple[str, float]:
    """
    Transcribe audio file. Returns (text, confidence 0..1).
    Part 1: Response time logging; default language ar.
    """
    lang = language or WHISPER_LANGUAGE
    start = time.perf_counter()
    model = get_whisper_model()
    try:
        segments, info = model.transcribe(
            file_path,
            language=lang,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        # Use language probability as rough confidence if available
        confidence = getattr(info, "language_probability", 0.9) or 0.9
        elapsed = time.perf_counter() - start
        logger.info(
            "STT completed: path=%s duration_sec=%.2f len=%d",
            file_path, elapsed, len(text),
            extra={"stt_duration_sec": round(elapsed, 2), "transcription_length": len(text)},
        )
        return text, float(confidence)
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.exception("STT failed: path=%s duration_sec=%.2f error=%s", file_path, elapsed, e)
        raise
