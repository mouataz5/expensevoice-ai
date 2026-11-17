"""Grounding check: were the numbers the model returned actually spoken?

The extraction prompt tells the model not to invent numbers, but a prompt is not
a guarantee. This check compares the quantity and unit price against the numbers
found in the transcript. A value that does not appear there is reported as
ungrounded, and the quality gate sends the purchase to the employee with that
field highlighted instead of presenting it as a confident answer.

Handles Western and Arabic-Indic digits, decimal commas ("12,5") and thousands
separators ("1 200", "1.200"). Numbers spoken as words ("عشرين", "vingt") are not
parsed, so they surface as ungrounded: a false alarm costs one look from a human,
a missed hallucination costs money.
"""
from __future__ import annotations

import re

from app.schemas.extraction import ExtractedPurchase

_ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
# A number, optionally with grouped thousands and a decimal part.
_NUMBER_RE = re.compile(r"\d{1,3}(?:[ . ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?")

_TOLERANCE = 0.005


def numbers_in_text(text: str) -> set[float]:
    """All numeric values in a transcript, under both separator readings."""
    values: set[float] = set()
    normalized = (text or "").translate(_ARABIC_INDIC).replace("٫", ".").replace("٬", " ")
    for token in _NUMBER_RE.findall(normalized):
        compact = token.replace(" ", "").replace(" ", "")
        # "1.200" may be one thousand two hundred or one point two: keep both readings.
        candidates = {compact.replace(",", ".")}
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", compact):
            candidates.add(compact.replace(".", ""))
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+,\d+", compact):
            candidates.add(compact.replace(".", "").replace(",", "."))
        for c in candidates:
            try:
                values.add(float(c))
            except ValueError:
                continue
    return values


def _spoken(value: float, spoken: set[float]) -> bool:
    return any(abs(value - s) <= _TOLERANCE for s in spoken)


def ungrounded_fields(transcript: str, extracted: ExtractedPurchase) -> list[str]:
    """Names of numeric fields whose value does not appear in the transcript.

    A total may be spoken instead of a unit price ("20 bags for 900 dinars"), so
    unit_price also counts as grounded when quantity and a spoken total explain it.
    A quantity of 1 is always accepted: it is what a speaker means by "a can of oil".
    """
    spoken = numbers_in_text(transcript)
    missing: list[str] = []

    qty = float(extracted.quantity)
    if qty != 1 and not _spoken(qty, spoken):
        missing.append("quantity")

    price = float(extracted.unit_price)
    price_ok = _spoken(price, spoken) or any(
        abs(price * qty - s) <= max(_TOLERANCE, 0.001 * s) for s in spoken
    )
    # A price of 0 means the model had nothing to go on; treat it as unspoken.
    if price == 0 or not price_ok:
        missing.append("unit_price")
    return missing
