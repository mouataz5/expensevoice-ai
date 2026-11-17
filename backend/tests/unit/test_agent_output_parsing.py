import pytest

from app.agent.output_parsing import ExtractionOutputError, parse_extraction, repair_instruction

ALLOWED = ["charge_variable_autre", "vente_poussins"]
VALID = (
    '{"product_name":"engrais","category":"charge_variable_autre","quantity":20,'
    '"unit_price":45,"total_amount":900,"currency":"TND","confidence":0.9,"notes":null}'
)


def test_valid_output_is_accepted():
    p = parse_extraction(VALID, ALLOWED)
    assert p.quantity == 20 and p.unit_price == 45


def test_code_fences_and_surrounding_prose_are_tolerated():
    assert parse_extraction(f"```json\n{VALID}\n```", ALLOWED).quantity == 20
    assert parse_extraction(f"Here is the JSON: {VALID} done", ALLOWED).quantity == 20


@pytest.mark.parametrize(
    "raw,reason",
    [
        ("", "empty_output"),
        ("I could not understand the audio", "not_json"),
        ("[1, 2]", "not_an_object"),
        ('{"product_name":"engrais","category":"charge_variable_autre"}', "schema_mismatch"),
    ],
)
def test_invalid_outputs_raise_with_a_reason(raw, reason):
    with pytest.raises(ExtractionOutputError) as e:
        parse_extraction(raw, ALLOWED)
    assert e.value.reason == reason


def test_missing_price_is_not_silently_defaulted():
    raw = (
        '{"product_name":"engrais","category":"charge_variable_autre","quantity":20,'
        '"total_amount":0,"currency":"TND","confidence":0.9}'
    )
    with pytest.raises(ExtractionOutputError) as e:
        parse_extraction(raw, ALLOWED)
    assert "unit_price" in e.value.detail


def test_category_outside_policy_is_rejected():
    raw = VALID.replace("charge_variable_autre", "achat_aliment")
    with pytest.raises(ExtractionOutputError) as e:
        parse_extraction(raw, ALLOWED)
    assert e.value.reason == "category_not_in_policy"


def test_repair_instruction_names_the_failure():
    msg = repair_instruction(ExtractionOutputError("schema_mismatch", "unit_price"))
    assert "schema_mismatch" in msg and "unit_price" in msg
