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


def normalize_tnd_amount(value: str | None) -> float | None:
    """Alias : même sémantique que `normalize_tunisian_invoice_amount`."""
    return normalize_tunisian_invoice_amount(value)


def normalize_tunisian_amount(value: str | None) -> float | None:
    """Alias explicite pour montants factures TN (espaces / points millimes)."""
    return normalize_tunisian_invoice_amount(value)


def normalize_tunisian_invoice_amount(value: str | None) -> float | None:
    """
    Interprète un montant tel qu’imprimé sur factures TN (millimes après le dernier séparateur).

    Exemples : 12.045.000 → 12045.000 ; 1.000 → 1.000 ; 22 176,003 → 22176.003.
    Ne remplace pas le parseur métier : délègue à la même logique que `parse_amount_token`.
    """
    raw = (value or "").strip()
    if not raw:
        return None

    # 1) Essai parseur métier existant (prioritaire pour compatibilité).
    parsed = parse_amount_token(raw)
    if parsed is not None:
        return parsed

    # 2) Fallback robuste pour formats tunisiens avec séparateurs d'espace.
    # Ex: "8 229.000", "24 687.000", "53 137.070", "83 300", "1 071 000"
    t = raw.replace("\u00a0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"[^\d,.\- ]", "", t)
    if not t:
        return None

    sign = -1.0 if t.startswith("-") else 1.0
    t = t.lstrip("-").strip()
    if not t:
        return None

    if "," in t and "." in t:
        # Cas mixte FR/TN: "22 176,003" -> 22176.003
        left, right = t.rsplit(",", 1)
        if right.isdigit():
            left_clean = re.sub(r"[ .]", "", left)
            merged = f"{left_clean}.{right}"
            try:
                return sign * float(merged)
            except ValueError:
                return None

    if "." in t:
        # "24 687.000" -> 24687.000 ; "1.071.000" -> 1071.000
        left, right = t.rsplit(".", 1)
        if right.isdigit():
            left_clean = re.sub(r"[ .]", "", left)
            merged = f"{left_clean}.{right}"
            try:
                return sign * float(merged)
            except ValueError:
                return None

    # Espaces uniquement sans ambiguïté millimes : relève surtout les cas non couverts par parse_amount_token.
    if re.fullmatch(r"\d{1,3}(?: \d{3})+", t):
        try:
            return sign * float(t.replace(" ", ""))
        except ValueError:
            return None

    if t.isdigit():
        try:
            return sign * float(t)
        except ValueError:
            return None

    return None


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
