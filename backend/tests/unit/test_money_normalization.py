"""Tests parsing montants (TND/FR) via utils/money."""
import pytest

from app.utils.money import normalize_number_like_string, parse_amount_token, to_float_safe


def test_parse_amount_multi_separators() -> None:
    assert parse_amount_token("15.575,000") == pytest.approx(15575.0)
    assert parse_amount_token("15 575,000") == pytest.approx(15575.0)
    assert parse_amount_token("5 810,000") == pytest.approx(5810.0)


def test_to_float_safe_from_str() -> None:
    assert to_float_safe("22 176,003") == pytest.approx(22176.003)


def test_normalize_number_like_string_nbsp() -> None:
    assert normalize_number_like_string("1\u00a0234,50") == "1 234,50"

