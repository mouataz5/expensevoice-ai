"""Approval guardrail: when must a manager approve a confirmed purchase?

The ``approval_workflow`` policy lets a director turn manager approval off to save
time. Before this module, turning it off auto-approved *every* purchase, including
ones above the per-purchase limit. Now the switch only covers routine purchases:
a purchase that breaks a spending rule always goes to a manager.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ApprovalRequirement(BaseModel):
    requires_approval: bool
    reasons: list[str] = Field(default_factory=list)


def approval_requirement(
    *,
    workflow_rule: dict,
    limits_rule: dict,
    total_amount: float,
    from_voice: bool,
    extraction_confidence: float | None,
    min_voice_confidence: float = 0.7,
) -> ApprovalRequirement:
    """Decide if a manager must approve. Pure function, no database access."""
    if bool(workflow_rule.get("require_admin_approval", True)):
        return ApprovalRequirement(requires_approval=True, reasons=["policy_requires_admin_approval"])

    reasons: list[str] = []
    max_per_purchase = float(limits_rule.get("max_per_purchase", 0) or 0)
    if max_per_purchase > 0 and total_amount > max_per_purchase:
        reasons.append("above_max_per_purchase")

    if from_voice and extraction_confidence is not None and extraction_confidence < min_voice_confidence:
        reasons.append("low_confidence_voice_extraction")

    return ApprovalRequirement(requires_approval=bool(reasons), reasons=reasons or ["routine_purchase"])
