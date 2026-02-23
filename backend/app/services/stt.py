import os
from functools import lru_cache

from faster_whisper import WhisperModel


@lru_cache(maxsize=1)
def get_whisper_model() -> WhisperModel:
    model_size = os.getenv("WHISPER_MODEL", "small")
    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

    return WhisperModel(model_size, device=device, compute_type=compute_type)


def transcribe_audio(file_path: str, language: str | None = None) -> str:
    model = get_whisper_model()

    segments, _info = model.transcribe(
        file_path,
        language=language,
        vad_filter=True,
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return text
