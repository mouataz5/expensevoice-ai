import pytest

from app.agent.grounding import numbers_in_text, ungrounded_fields
from app.agent.quality_gate import evaluate_extraction
from app.schemas.extraction import ExtractedPurchase


def purchase(qty=20, price=45.0, total=None, conf=0.9):
    return ExtractedPurchase(
        product_name="engrais",
        category="charge_variable_autre",
        quantity=qty,
        unit_price=price,
        total_amount=qty * price if total is None else total,
        currency="TND",
        confidence=conf,
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        ("20 bags at 45 dinars", {20.0, 45.0}),
        ("prix 12,5 dinars", {12.5}),
        ("اشريت ٢٠ كيس ب ٤٥ دينار", {20.0, 45.0}),
        ("total 1 200 dinars", {1200.0}),
        ("1.200 dinars", {1200.0, 1.2}),
    ],
)
def test_numbers_in_text(text, expected):
    assert expected <= numbers_in_text(text)


def test_spoken_numbers_are_grounded():
    assert ungrounded_fields("I bought 20 bags of fertiliser at 45 dinars", purchase()) == []


def test_price_from_spoken_total_is_grounded():
    # "20 bags for 900 dinars": unit price 45 is derived, not spoken.
    assert ungrounded_fields("20 bags of fertiliser for 900 dinars", purchase()) == []


def test_invented_price_is_flagged():
    assert ungrounded_fields("I bought 20 bags of fertiliser", purchase()) == ["unit_price"]


def test_invented_quantity_is_flagged():
    assert ungrounded_fields("fertiliser at 45 dinars", purchase(qty=20)) == ["quantity"]


def test_single_item_without_number_is_fine():
    assert ungrounded_fields("one can of oil, 18 dinars", purchase(qty=1, price=18)) == []


def gate(text, p, stt=0.9, **kw):
    return evaluate_extraction(transcript=text, extracted=p, stt_confidence=stt, **kw)


def test_clean_extraction_is_ready():
    d = gate("20 bags at 45 dinars", purchase())
    assert d.route == "ready" and d.reasons == ["all_checks_passed"]


def test_hallucinated_price_needs_attention():
    d = gate("I bought 20 bags", purchase())
    assert d.route == "needs_attention"
    assert "not_in_transcript:unit_price" in d.reasons
    assert d.flagged_fields == ["unit_price"]


def test_low_stt_and_model_confidence_need_attention():
    d = gate("20 bags at 45 dinars", purchase(conf=0.4), stt=0.3)
    assert d.route == "needs_attention"
    assert {"low_transcription_confidence", "low_model_confidence"} <= set(d.reasons)


def test_model_total_disagreement_flags_both_numbers():
    d = gate("20 bags at 45 dinars", purchase(total=450))
    assert "model_total_disagrees_with_quantity_x_price" in d.reasons
    assert set(d.flagged_fields) == {"quantity", "unit_price"}


def test_above_limit_needs_attention():
    d = gate("20 bags at 45 dinars", purchase(), max_per_purchase=500)
    assert "above_max_per_purchase" in d.reasons


def test_failed_extraction_goes_to_manual_entry():
    d = gate("blah", None, extraction_error="schema_mismatch")
    assert d.route == "manual_entry" and d.reasons == ["extraction_failed:schema_mismatch"]


def test_empty_transcript_goes_to_manual_entry():
    assert gate("   ", purchase()).route == "manual_entry"
