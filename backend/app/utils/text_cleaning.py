"""Nettoyage léger du texte OCR."""
from __future__ import annotations

import re


def collapse_whitespace(text: str) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", (text or "").strip())


def normalize_newlines(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def strip_control_chars(text: str) -> str:
    return "".join(ch for ch in (text or "") if ch == "\n" or ord(ch) >= 32)


def clean_ocr_text(text: str) -> str:
    t = strip_control_chars(normalize_newlines(text))
    lines = [collapse_whitespace(ln) for ln in t.split("\n")]
    return "\n".join(ln for ln in lines if ln).strip()


# Montants style TN / EU : points = milliers, virgule = décimales (ex: 15.575,000)
_AMT_DOT_THOU = re.compile(
    r"\b(\d{1,3}(?:\.\d{3})+(?:,\d{1,4})?|\d{1,3}(?:\.\d{3})+)\b"
)


def normalize_european_amount_tokens(text: str) -> str:
    """
    Formats TN / EU : points = milliers, dernier bloc .xxx souvent millimes (ex: 15.575.000 → 15575,000).
    Deux blocs seulement : 1.500 → 1500 (milliers).
    Avec virgule décimale explicite : 15.575,000 → 15575,000.
    """

    def repl(m: re.Match[str]) -> str:
        block = m.group(1)
        if "," in block:
            intpart, decpart = block.rsplit(",", 1)
            intpart = intpart.replace(".", "")
            return f"{intpart},{decpart}"
        if "." in block:
            parts = block.split(".")
            if len(parts) >= 3 and len(parts[-1]) == 3 and parts[-1].isdigit():
                frac = parts[-1]
                int_join = "".join(parts[:-1])
                return f"{int_join},{frac}"
            if len(parts) >= 2:
                return "".join(parts)
        return block

    return _AMT_DOT_THOU.sub(repl, text or "")


_OCR_LETTER_IN_NUMBER = re.compile(
    r"\b(?=[\dOIlSs]+[\d,.]*)([0-9OIlSs]{2,}(?:[.,][0-9OIlSs]+)?)\b",
    re.IGNORECASE,
)


def fix_common_ocr_letter_digit_confusions(token: str) -> str:
    """O→0, l|I→1 sur tokens exclusivement numériques + séparateurs."""
    t = token
    if not t or not re.search(r"\d|[oOiIlL]", t, re.I):
        return t
    trans = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "L": "1", "S": "5", "s": "5"})
    return t.translate(trans)


def fix_ocr_confusions_in_numeric_tokens(text: str) -> str:
    """Corrige O/l confondus avec 0/1 dans des morceaux ressemblant à des montants."""

    def sub_num(m: re.Match[str]) -> str:
        return fix_common_ocr_letter_digit_confusions(m.group(0))

    return _OCR_LETTER_IN_NUMBER.sub(sub_num, text or "")


_TN_DECIMAL_COMMA = re.compile(r"\b(\d{1,9})\s*,\s*(\d{1,4})\b(?!\d)")


def tn_millimes_comma_to_dot(text: str) -> str:
    """
    Après normalise_european_amount_tokens : 15575,000 → 15575.000
    (décimal avec point, sans séparateurs de milliers — plus stable pour le LLM).
    """

    def repl(m: re.Match[str]) -> str:
        return f"{m.group(1)}.{m.group(2)}"

    return _TN_DECIMAL_COMMA.sub(repl, text or "")


def cleaned_invoice_text_for_llm(text: str) -> str:
    """
    Chaîne optimisée pour le LLM : espaces, montants EU/TN normalisés, confusions OCR légères.
    """
    t = clean_ocr_text(text)
    t = normalize_european_amount_tokens(t)
    t = fix_ocr_confusions_in_numeric_tokens(t)
    t = tn_millimes_comma_to_dot(t)
    return t


def invoice_text_raw_and_cleaned(ocr_raw: str) -> tuple[str, str]:
    """Espaces/contrôles seuls vs chaîne envoyée au LLM (montants + OCR fixes)."""
    raw = clean_ocr_text(ocr_raw)
    cleaned = cleaned_invoice_text_for_llm(ocr_raw)
    return raw, cleaned
