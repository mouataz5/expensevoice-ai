"""
STT — façade vers `speech.whisper_service` (faster-whisper / CTranslate2).

Conservé pour compatibilité `purchase_processing` et imports existants.
"""
from __future__ import annotations

from app.services.speech.whisper_service import transcribe_file


def transcribe_audio(
    file_path: str,
    language: str | None = None,
) -> tuple[str, float]:
    """
    Transcribe audio file. Returns (text, confidence 0..1).
    """
    out = transcribe_file(file_path, language=language)
    return out.get("text") or "", float(out.get("confidence") or 0.0)
