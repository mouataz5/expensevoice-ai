"""Tests normalisation dates → ISO."""
from app.utils.dates import is_valid_iso_date, parse_date_to_iso


def test_parse_dd_mm_yyyy() -> None:
    assert parse_date_to_iso("16/01/2026") == "2026-01-16"
    assert parse_date_to_iso("16-01-2026") == "2026-01-16"
    assert parse_date_to_iso("16.01.2026") == "2026-01-16"


def test_parse_already_iso() -> None:
    assert parse_date_to_iso("2026-01-16") == "2026-01-16"


def test_invalid_date() -> None:
    assert parse_date_to_iso("not a date") is None
    assert parse_date_to_iso("") is None
    assert is_valid_iso_date("2026-02-30") is False

