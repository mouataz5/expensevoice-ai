"""Encode image file en base64 (API multimodale Ollama / LLaVA)."""
from __future__ import annotations

import base64
from pathlib import Path


def image_file_to_base64(path: str | Path) -> str:
    """Contenu brut base64 (sans préfixe data:)."""
    data = Path(path).read_bytes()
    return base64.b64encode(data).decode("ascii")


__all__ = ["image_file_to_base64"]
