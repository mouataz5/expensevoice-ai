"""Formats montants tunisiens (espaces milliers + décimal point ou entier)."""
from __future__ import annotations

import pytest

from app.utils.money import normalize_tunisian_invoice_amount, parse_tunisian_number


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("8 229.000", 8229.0),
        ("24 687.000", 24687.0),
        ("83 300", 83300.0),
        ("1 071 000", 1071000.0),
        ("53 137.070", 53137.07),
    ],
)
def test_parse_tunisian_number_spaced(raw: str, expected: float) -> None:
    assert parse_tunisian_number(raw) == pytest.approx(expected)
    assert normalize_tunisian_invoice_amount(raw) == pytest.approx(expected)
