"""
Post-traitement léger des transcriptions vocales avant extraction JSON (Groq) ou pipeline facture.

Ne remplace pas Whisper : normalise Unicode, chiffres arabo-indiques, espaces.
"""
from __future__ import annotations

import re
import unicodedata

_AR_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789..")

__all__ = ["normalize_transcript_for_extraction"]


def normalize_transcript_for_extraction(text: str) -> str:
    """Normalisation conservative pour aligner chiffres et espaces sur l’extracteur métier."""
    t = unicodedata.normalize("NFKC", text or "")
    t = t.translate(_AR_DIGIT_MAP)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()
