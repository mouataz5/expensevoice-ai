"""
Normalisation des montants tunisiens pour le moteur de table dynamique.

Espaces = milliers, dernier groupe de 3 = millimes (même logique que le parseur métier).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from app.utils.money import normalize_tunisian_invoice_amount, parse_amount_token


def parse_tunisian_amount(value: str | None) -> Decimal | None:
    """
    Parse un libellé monétaire TN (facture / devis) en Decimal.

    Retourne None si non parseable. Ne fragmente pas un montant unique en plusieurs nombres.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    v = normalize_tunisian_invoice_amount(raw)
    if v is None:
        v = parse_amount_token(raw)
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


__all__ = ["parse_tunisian_amount"]
