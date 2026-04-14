"""
Speech-to-text service: Groq cloud Whisper (primary) with local faster-whisper fallback.

Primary: Groq whisper-large-v3-turbo — fast, accurate, handles Arabic dialects well.
Fallback: Local faster-whisper (CTranslate2, int8) when Groq API is unavailable.

Environment variables:
- GROQ_API_KEY: required for cloud STT (shared with LLM extraction)
- STT_PROVIDER: "groq" (default) | "local" — force a specific provider
- WHISPER_MODEL: local model name (default: turbo)
- WHISPER_DEVICE, WHISPER_COMPUTE_TYPE: local model config
- WHISPER_LANGUAGE: default language hint (default: ar)
- SPEECH_TRANSCRIBE_TIMEOUT_SEC: timeout for local thread (0 = disabled)
"""
from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

STT_PROVIDER = os.getenv("STT_PROVIDER", "groq").strip().lower()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "turbo")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "ar")
SPEECH_TRANSCRIBE_TIMEOUT_SEC = float(os.getenv("SPEECH_TRANSCRIBE_TIMEOUT_SEC", "0") or "0")

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper")

_HALLUCINATION_RE = re.compile(r"(\b\S+\b)(?:\s+\1){3,}")


def _is_hallucination(text: str) -> bool:
    """Detect Whisper hallucination: same word repeated 4+ times in a row."""
    if not text or len(text) < 10:
        return False
    words = text.split()
    if len(words) < 4:
        return False
    if _HALLUCINATION_RE.search(text):
        return True
    unique_ratio = len(set(words)) / len(words)
    return unique_ratio < 0.25


def _groq_available() -> bool:
    return bool(GROQ_API_KEY) and STT_PROVIDER != "local"


def _transcribe_groq(file_path: str, *, language: str | None) -> dict[str, Any]:
    from groq import Groq

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio introuvable: {file_path}")
    if path.stat().st_size < 64:
        raise ValueError("audio_empty")

    lang = None
    if language and language.strip().lower() not in ("", "auto"):
        lang = language.strip().lower()[:8]

    start = time.perf_counter()
    client = Groq(api_key=GROQ_API_KEY)

    with open(file_path, "rb") as f:
        result = client.audio.transcriptions.create(
            file=(path.name, f),
            model="whisper-large-v3-turbo",
            language=lang,
            response_format="verbose_json",
            temperature=0.0,
        )

    text = (result.text or "").strip()
    elapsed = time.perf_counter() - start

    confidence = 0.0
    if hasattr(result, "segments") and result.segments:
        probs = [s.avg_logprob for s in result.segments if hasattr(s, "avg_logprob") and s.avg_logprob]
        if probs:
            import math
            avg_log = sum(probs) / len(probs)
            confidence = min(1.0, max(0.0, math.exp(avg_log)))
    if confidence <= 0 and text:
        confidence = 0.85

    detected_lang = lang or WHISPER_LANGUAGE
    if hasattr(result, "language") and result.language:
        detected_lang = result.language

    logger.info(
        "groq_whisper_done",
        extra={
            "pipeline_stage": "whisper",
            "component": "stt_groq",
            "duration_ms": round(elapsed * 1000, 2),
            "audio_basename": path.name,
            "language": detected_lang,
            "text_len": len(text),
            "confidence": round(confidence, 3),
        },
    )

    return {
        "text": text,
        "language": detected_lang or "unknown",
        "confidence": min(1.0, max(0.0, confidence)),
        "duration_sec": round(elapsed, 3),
        "provider": "groq",
    }


# ── Local faster-whisper fallback ──


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
def _get_local_model():
    from faster_whisper import WhisperModel
    device = _resolve_device()
    logger.info(
        "Loading local Whisper: model=%s device=%s compute=%s",
        WHISPER_MODEL, device, WHISPER_COMPUTE_TYPE,
    )
    return WhisperModel(WHISPER_MODEL, device=device, compute_type=WHISPER_COMPUTE_TYPE)


def _transcribe_local(file_path: str, *, language: str | None) -> dict[str, Any]:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio introuvable: {file_path}")
    if path.stat().st_size < 64:
        raise ValueError("audio_empty")

    whisper_lang: str | None = None
    if language and language.strip().lower() not in ("", "auto"):
        whisper_lang = language.strip().lower()[:8]

    start = time.perf_counter()
    model = _get_local_model()
    segments, info = model.transcribe(str(path), language=whisper_lang, vad_filter=True)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    elapsed = time.perf_counter() - start

    detected = getattr(info, "language", None) or whisper_lang or WHISPER_LANGUAGE
    confidence = float(getattr(info, "language_probability", 0.0) or 0.0)
    if confidence <= 0 and text:
        confidence = 0.75
    if confidence <= 0:
        confidence = 0.0

    logger.info(
        "local_whisper_done",
        extra={
            "pipeline_stage": "whisper",
            "component": "stt_local",
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
        "provider": "local",
    }


# ── Public API ──


def transcribe_file(file_path: str, *, language: str | None = None) -> dict[str, Any]:
    """
    Transcribe audio file. Tries Groq cloud first, falls back to local.
    Returns: { "text", "language", "confidence", "duration_sec", "provider" }
    """
    if _groq_available():
        try:
            result = _transcribe_groq(file_path, language=language)
            if not _is_hallucination(result.get("text", "")):
                return result
            logger.warning(
                "Groq transcription looks like hallucination, falling back to local",
                extra={"text_preview": result.get("text", "")[:80]},
            )
        except Exception as e:
            logger.warning("Groq STT failed, falling back to local: %s", e)

    if STT_PROVIDER == "groq":
        logger.info("Groq failed/unavailable, trying local fallback")

    timeout = SPEECH_TRANSCRIBE_TIMEOUT_SEC
    if timeout and timeout > 0:
        fut = _executor.submit(_transcribe_local, file_path, language=language)
        try:
            return fut.result(timeout=timeout)
        except FuturesTimeout:
            logger.error("Local STT timeout after %.1fs for %s", timeout, file_path)
            raise TimeoutError("transcription_timeout") from None
    return _transcribe_local(file_path, language=language)


def transcribe_audio(file_path: str, language: str | None = None) -> dict[str, Any]:
    """Public alias for backward compatibility."""
    return transcribe_file(file_path, language=language)
