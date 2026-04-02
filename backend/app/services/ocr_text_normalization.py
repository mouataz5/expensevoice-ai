"""
Normalisation du texte OCR avant envoi LLM (nettoyage + hints dates/montants légers).
"""
from __future__ import annotations

import re

from app.utils.post_processing import fix_common_words
from app.utils.text_cleaning import cleaned_invoice_text_for_llm, clean_ocr_text


def normalize_ocr_for_llm(raw_text: str) -> str:
    """Nettoyage + normalisation montants / confusions OCR légères pour le LLM."""
    t = cleaned_invoice_text_for_llm(raw_text or "")
    t = fix_common_words(t, ocr_context=raw_text or "")
    # Normaliser tirets bizarres
    t = t.replace("\u2013", "-").replace("\u2014", "-")
    return t


def raw_cleaned_only(raw_text: str) -> str:
    """Nettoyage espaces / contrôle uniquement (sans réécriture des montants)."""
    t = clean_ocr_text(raw_text or "")
    return t.replace("\u2013", "-").replace("\u2014", "-")


def excerpt_for_debug(text: str, max_len: int = 4000) -> str:
    t = text or ""
    if len(t) <= max_len:
        return t
    return t[: max_len // 2] + "\n…\n" + t[-max_len // 2 :]


def detect_currency_hint(text: str) -> str | None:
    ul = (text or "").upper()
    if re.search(r"\bTND\b|\bDT\b|DINAR", ul):
        return "TND"
    if "EUR" in ul or " €" in text:
        return "EUR"
    if "USD" in ul or "$" in text:
        return "USD"
    return None
