"""Tests parsing montants (TND/FR) via utils/money."""
import pytest

from app.utils.money import (
    normalize_number_like_string,
    normalize_tunisian_invoice_amount,
    parse_amount_token,
    to_float_safe,
)


def test_parse_amount_multi_separators() -> None:
    assert parse_amount_token("15.575,000") == pytest.approx(15575.0)
    assert parse_amount_token("15 575,000") == pytest.approx(15575.0)
    assert parse_amount_token("5 810,000") == pytest.approx(5810.0)


def test_to_float_safe_from_str() -> None:
    assert to_float_safe("22 176,003") == pytest.approx(22176.003)


def test_normalize_number_like_string_nbsp() -> None:
    assert normalize_number_like_string("1\u00a0234,50") == "1 234,50"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("8 229.000", 8229.000),
        ("24 687.000", 24687.000),
        ("53 137.070", 53137.070),
        # OCR devis sans point décimal explicite (millimes = dernier groupe de 3)
        ("83 300", 83.300),
        ("1 071 000", 1071.000),
        ("6 913 900", 6913.900),
        ("44 723 000", 44723.000),
    ],
)
def test_normalize_tunisian_invoice_amount_with_spaced_thousands(raw: str, expected: float) -> None:
    assert normalize_tunisian_invoice_amount(raw) == pytest.approx(expected)


def test_parse_amount_token_devis_occlusion_patterns() -> None:
    """Captures typiques Abdouli / devis TN quand le point millimes manque sur l'OCR."""
    assert parse_amount_token("6 913 900") == pytest.approx(6913.9)
    assert parse_amount_token("83 300") == pytest.approx(83.3)
    assert parse_amount_token("83 300") == normalize_tunisian_invoice_amount("83 300")


def test_parse_amount_triplet_space_000_comma_millimes() -> None:
    """Export PDF / OCR : groupe de milliers se termine par 000 avant la virgule millimes."""
    assert parse_amount_token("142 000,000") == pytest.approx(142000.0)
    assert parse_amount_token("1 800,000") == pytest.approx(1800.0)


def test_parse_amount_stpa_qty_pu_fused_still_rejected() -> None:
    assert parse_amount_token("100 116,200") is None


def test_parse_amount_comma_grouped_like_pdf_export() -> None:
    """Rapports / exports avec virgules comme séparateurs (sans point millimes explicite)."""
    assert parse_amount_token("1,071,000") == pytest.approx(1071.0)
    assert parse_amount_token("30,000") == pytest.approx(30.0)
    assert parse_amount_token("577,530") == pytest.approx(577.53)
    assert normalize_tunisian_invoice_amount("44,723,000") == pytest.approx(44723.0)

