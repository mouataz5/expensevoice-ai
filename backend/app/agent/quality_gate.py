"""Quality gate: what happens to a voice purchase after extraction.

Three routes, decided by deterministic rules, never by the model:

- ``ready``           all checks passed; the employee confirms with one tap.
- ``needs_attention`` a usable draft, but specific fields are flagged for the
                      employee to check before confirming (reasons say which).
- ``manual_entry``    nothing trustworthy was extracted; the employee types it.

No route skips a human: the employee always confirms, and ``approval.py`` decides
whether a manager must approve as well. The gate decides how much the human is
asked to check, and records why, so the audit log explains every decision.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.agent.grounding import ungrounded_fields
from app.schemas.extraction import ExtractedPurchase

Route = Literal["ready", "needs_attention", "manual_entry"]

# Below this, Whisper's transcript is unreliable enough that every field is suspect.
MIN_STT_CONFIDENCE = 0.55
# The model's self-reported confidence is weak evidence; it can only lower the route.
MIN_MODEL_CONFIDENCE = 0.7


class GateDecision(BaseModel):
    route: Route
    reasons: list[str] = Field(default_factory=list)
    flagged_fields: list[str] = Field(default_factory=list)


def evaluate_extraction(
    *,
    transcript: str,
    extracted: ExtractedPurchase | None,
    stt_confidence: float | None,
    extraction_error: str | None = None,
    max_per_purchase: float = 0.0,
) -> GateDecision:
    """Route one extraction. Pure function: same inputs, same decision."""
    if not (transcript or "").strip():
        return GateDecision(route="manual_entry", reasons=["empty_transcript"])
    if extracted is None:
        return GateDecision(
            route="manual_entry",
            reasons=[f"extraction_failed:{extraction_error or 'unknown'}"],
        )

    reasons: list[str] = []
    flagged: list[str] = []

    for field in ungrounded_fields(transcript, extracted):
        reasons.append(f"not_in_transcript:{field}")
        flagged.append(field)

    if stt_confidence is not None and stt_confidence < MIN_STT_CONFIDENCE:
        reasons.append("low_transcription_confidence")

    if extracted.confidence < MIN_MODEL_CONFIDENCE:
        reasons.append("low_model_confidence")

    total = round(extracted.quantity * extracted.unit_price, 3)
    if abs(total - extracted.total_amount) > max(0.01, 0.01 * total) and extracted.total_amount > 0:
        # The server always recomputes the total; a disagreement means the model
        # misunderstood quantity or price, so both are worth a look.
        reasons.append("model_total_disagrees_with_quantity_x_price")
        flagged.extend(f for f in ("quantity", "unit_price") if f not in flagged)

    if max_per_purchase > 0 and total > max_per_purchase:
        reasons.append("above_max_per_purchase")

    if not reasons:
        return GateDecision(route="ready", reasons=["all_checks_passed"])
    return GateDecision(route="needs_attention", reasons=reasons, flagged_fields=flagged)
