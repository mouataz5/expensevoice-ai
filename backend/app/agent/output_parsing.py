"""Strict parsing of the LLM's purchase extraction.

A model response is only accepted if it is a JSON object that validates against
``ExtractedPurchase`` and uses a category from the active policy. Anything else
raises ``ExtractionOutputError`` with a short reason, so the caller can retry once
with that reason or send the purchase to manual entry. Missing fields are never
filled with silent defaults: a price the speaker did not say must not become 0.
"""
from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.schemas.extraction import ExtractedPurchase

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class ExtractionOutputError(ValueError):
    """The model's output could not be turned into a valid purchase."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def _load_json_object(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        raise ExtractionOutputError("empty_output")
    text = _FENCE_RE.sub("", text).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # Some models wrap the object in prose; accept the outermost {...} only.
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ExtractionOutputError("not_json", text[:120]) from None
        try:
            obj = json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            raise ExtractionOutputError("not_json", str(e)) from None
    if not isinstance(obj, dict):
        raise ExtractionOutputError("not_an_object", type(obj).__name__)
    return obj


def parse_extraction(
    raw: str,
    allowed_categories: list[str] | None = None,
) -> ExtractedPurchase:
    """Parse and validate one model response. Raises ``ExtractionOutputError``."""
    obj = _load_json_object(raw)
    try:
        purchase = ExtractedPurchase(**obj)
    except ValidationError as e:
        fields = sorted({".".join(str(p) for p in err["loc"]) for err in e.errors()})
        raise ExtractionOutputError("schema_mismatch", ", ".join(fields)) from None
    if allowed_categories and purchase.category not in allowed_categories:
        raise ExtractionOutputError("category_not_in_policy", purchase.category)
    return purchase


def repair_instruction(error: ExtractionOutputError) -> str:
    """Message sent back to the model on the single retry."""
    return (
        "Your previous answer was rejected by the validator "
        f"({error.reason}{': ' + error.detail if error.detail else ''}). "
        "Return ONLY one JSON object that matches the schema exactly. "
        "Use only categories from the allowed list. If a value was not spoken, "
        "do not invent it: give your best estimate and set confidence below 0.5."
    )
