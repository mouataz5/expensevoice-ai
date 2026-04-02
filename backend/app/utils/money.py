"""Parsing et normalisation des montants (Tunisie / France)."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any


def parse_amount_token(raw: str | None) -> float | None:
    """Délègue au parseur métier existant (formats TN/FR)."""
    if raw is None:
        return None
    from app.services.invoice_extraction import _parse_amount_token as _p

    return _p(str(raw).strip())


def normalize_number_like_string(s: str) -> str:
    """Normalise une chaîne ressemblant à un montant pour affichage / LLM hint."""
    t = (s or "").strip().replace("\u00a0", " ")
    t = re.sub(r"\s+", " ", t)
    return t


def to_float_safe(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return parse_amount_token(v)
    try:
        return float(Decimal(str(v)))
    except (InvalidOperation, ValueError, TypeError):
        return None
