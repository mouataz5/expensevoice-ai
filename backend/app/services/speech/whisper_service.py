"""
Whisper « insanely fast » en production : **faster-whisper** (CTranslate2, quant int8).

Aligné avec les objectifs du projet *Insanely Fast Whisper* (latence faible, batch VAD)
sans dépendre du package HF expérimental — même famille d’optimisations (distil/turbo).

Variables d’environnement :
- WHISPER_MODEL (défaut: turbo)
- WHISPER_DEVICE, WHISPER_COMPUTE_TYPE
- WHISPER_LANGUAGE : langue par défaut si non auto
- SPEECH_TRANSCRIBE_TIMEOUT_SEC : timeout thread (0 = désactivé)
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from functools import lru_cache
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "turbo")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "ar")
SPEECH_TRANSCRIBE_TIMEOUT_SEC = float(os.getenv("SPEECH_TRANSCRIBE_TIMEOUT_SEC", "0") or "0")

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper")


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
    device = _resolve_device()
    logger.info(
        "Loading Whisper (faster-whisper): model=%s device=%s compute=%s",
        WHISPER_MODEL,
        device,
        WHISPER_COMPUTE_TYPE,
    )
    return WhisperModel(WHISPER_MODEL, device=device, compute_type=WHISPER_COMPUTE_TYPE)


def _transcribe_impl(
    file_path: str,
    *,
    language: str | None,
) -> dict[str, Any]:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio introuvable: {file_path}")
    if path.stat().st_size < 64:
        raise ValueError("audio_empty")

    whisper_lang: str | None
    if language is None or (isinstance(language, str) and language.strip().lower() in ("", "auto")):
        whisper_lang = None
    else:
        whisper_lang = language.strip().lower()[:8]

    start = time.perf_counter()
    model = get_whisper_model()
    segments, info = model.transcribe(
        str(path),
        language=whisper_lang,
        vad_filter=True,
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    elapsed = time.perf_counter() - start

    detected = getattr(info, "language", None) or whisper_lang or WHISPER_LANGUAGE
    confidence = float(getattr(info, "language_probability", 0.0) or 0.0)
    if confidence <= 0 and text:
        confidence = 0.75
    if confidence <= 0:
        confidence = 0.0

    logger.info(
        "whisper_transcribe_done",
        extra={
            "pipeline_stage": "whisper",
            "component": "stt",
            "duration_ms": round(elapsed * 1000, 2),
            "audio_basename": path.name,
            "language": str(detected) if detected else None,
            "text_len": len(text),
        },
    )

    return {
        "text": text,
        "language": str(detected) if detected else "unknown",
        "confidence": min(1.0, max(0.0, confidence)),
        "duration_sec": round(elapsed, 3),
    }


def transcribe_file(
    file_path: str,
    *,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Transcription fichier audio (wav, mp3, m4a, … supportés par ffmpeg/faster-whisper).

    Retour :
        { "text", "language", "confidence", "duration_sec" }
    """
    timeout = SPEECH_TRANSCRIBE_TIMEOUT_SEC
    if timeout and timeout > 0:
        fut = _executor.submit(_transcribe_impl, file_path, language=language)
        try:
            return fut.result(timeout=timeout)
        except FuturesTimeout:
            logger.error("STT timeout after %.1fs for %s", timeout, file_path)
            raise TimeoutError("transcription_timeout") from None
    return _transcribe_impl(file_path, language=language)


def transcribe_audio(file_path: str, language: str | None = None) -> dict[str, Any]:
    """Alias explicite pour l’API publique."""
    return transcribe_file(file_path, language=language)
