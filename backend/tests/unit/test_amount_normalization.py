"""parse_tunisian_amount (Decimal) — formats devis / factures TN."""
from decimal import Decimal

import pytest

from app.utils.amount_normalization import parse_tunisian_amount


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("8 229.000", Decimal("8229")),
        ("24 687.000", Decimal("24687")),
        ("53 137.070", Decimal("53137.070")),
        ("83 300", Decimal("83.300")),
        ("1 071 000", Decimal("1071")),
        ("44 723.000", Decimal("44723")),
    ],
)
def test_parse_tunisian_amount_examples(raw: str, expected: Decimal) -> None:
    got = parse_tunisian_amount(raw)
    assert got is not None
    assert got == expected


def test_parse_tunisian_amount_empty() -> None:
    assert parse_tunisian_amount("") is None
    assert parse_tunisian_amount(None) is None
