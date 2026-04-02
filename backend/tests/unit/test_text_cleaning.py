"""Nettoyage OCR / montants EU-TN."""

from app.utils.text_cleaning import (
    clean_ocr_text,
    cleaned_invoice_text_for_llm,
    fix_common_ocr_letter_digit_confusions,
    normalize_european_amount_tokens,
)


def test_normalize_dot_thousands_with_comma_decimal() -> None:
    s = "Sous-Total: 15.575,000 TND"
    out = normalize_european_amount_tokens(s)
    assert "15575,000" in out.replace(" ", "")


def test_normalize_dot_thousands_tn_millimes() -> None:
    s = "Total 15.575.000"
    out = normalize_european_amount_tokens(s)
    assert "15575,000" in out.replace(" ", "")


def test_normalize_two_group_thousands() -> None:
    s = "QTE 1.500"
    out = normalize_european_amount_tokens(s)
    assert "1500" in out.replace(" ", "")


def test_clean_ocr_collapses_space() -> None:
    assert clean_ocr_text("a  \n  b") == "a\nb"


def test_fix_o_in_amount() -> None:
    assert fix_common_ocr_letter_digit_confusions("1O50,000") == "1050,000"


def test_cleaned_invoice_dot_decimal_millimes() -> None:
    s = "Total TND 15.575.000"
    out = cleaned_invoice_text_for_llm(s)
    assert "15575.000" in out.replace(" ", "")
