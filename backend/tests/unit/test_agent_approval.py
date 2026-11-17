from app.agent.approval import approval_requirement

LIMITS = {"max_per_purchase": 500, "daily_limit_default": 1500}


def req(workflow, total, from_voice=False, conf=None):
    return approval_requirement(
        workflow_rule=workflow,
        limits_rule=LIMITS,
        total_amount=total,
        from_voice=from_voice,
        extraction_confidence=conf,
    )


def test_policy_requiring_approval_always_requires_it():
    r = req({"require_admin_approval": True}, 10)
    assert r.requires_approval and r.reasons == ["policy_requires_admin_approval"]


def test_missing_policy_defaults_to_requiring_approval():
    assert req({}, 10).requires_approval


def test_routine_purchase_is_auto_approved_when_policy_allows():
    r = req({"require_admin_approval": False}, 120)
    assert not r.requires_approval and r.reasons == ["routine_purchase"]


def test_purchase_above_limit_still_needs_a_manager():
    # Regression: with approval switched off, this used to be auto-approved.
    r = req({"require_admin_approval": False}, 900)
    assert r.requires_approval and r.reasons == ["above_max_per_purchase"]


def test_low_confidence_voice_purchase_still_needs_a_manager():
    r = req({"require_admin_approval": False}, 120, from_voice=True, conf=0.4)
    assert r.requires_approval and r.reasons == ["low_confidence_voice_extraction"]
