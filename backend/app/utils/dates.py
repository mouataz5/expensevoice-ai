"""Normalisation des dates vers ISO YYYY-MM-DD."""
from __future__ import annotations

import re
from datetime import datetime


def parse_date_to_iso(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()
    # YYYY-MM-DD
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return s
        except ValueError:
            return None
    # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    m2 = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b", s)
    if m2:
        d, mo, y = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def is_valid_iso_date(s: str | None) -> bool:
    if not s:
        return False
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        return False
    try:
        datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return True
    except ValueError:
        return False
