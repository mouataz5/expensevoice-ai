"""Pipeline wiring: STT -> extraction -> quality gate -> purchase + audit record.
Database, speech-to-text and the LLM are replaced with fakes."""
import uuid
from types import SimpleNamespace

import pytest

from app.agent.output_parsing import ExtractionOutputError
from app.schemas.extraction import ExtractedPurchase
from app.services import purchase_processing as pp


class FakeResult:
    def __init__(self, obj):
        self.obj = obj

    def scalar_one_or_none(self):
        return self.obj


class FakeDB:
    def __init__(self, purchase):
        self.purchase = purchase

    def execute(self, _stmt):
        return FakeResult(self.purchase)

    def get(self, _model, _id):
        return SimpleNamespace(id=uuid.uuid4(), role="employee")

    def add(self, _obj):
        pass

    def commit(self):
        pass

    def refresh(self, _obj):
        pass


@pytest.fixture
def env(monkeypatch):
    purchase = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), processing_status="processing")
    audits: list[dict] = []
    monkeypatch.setattr(pp, "get_allowed_categories", lambda db: ["charge_variable_autre"])
    monkeypatch.setattr(pp, "_get_policy", lambda db, t: {"max_per_purchase": 500})
    monkeypatch.setattr(pp, "audit_log", lambda db, **kw: audits.append(kw))

    def configure(transcript="20 sacs engrais a 45 dinars", stt_conf=0.9, extraction=None, error=None):
        monkeypatch.setattr(pp, "transcribe_audio", lambda path, language=None: (transcript, stt_conf))

        async def fake_extract(text, transaction_type=None, allowed_categories=None):
            if error:
                raise error
            return extraction

        monkeypatch.setattr(pp, "extract_purchase_fields", fake_extract)
        decision = pp.run_stt_then_extraction(purchase.id, "a.wav", None, "buy", FakeDB(purchase))
        return decision, purchase, audits

    return configure


def good(price=45.0):
    return ExtractedPurchase(
        product_name="engrais", category="charge_variable_autre", quantity=20,
        unit_price=price, total_amount=20 * price, currency="TND", confidence=0.9,
    )


def test_clean_voice_purchase_is_ready_and_audited(env):
    decision, purchase, audits = env(transcript="20 sacs engrais a 12 dinars", extraction=good(price=12))
    assert decision.route == "ready"
    assert purchase.total_amount == 240 and purchase.processing_status == "ready_for_review"
    assert audits[-1]["action"] == "extraction_quality_gate"
    assert audits[-1]["metadata"]["route"] == "ready"


def test_purchase_above_policy_limit_needs_attention(env):
    decision, _, _ = env(extraction=good(price=45))  # 900 TND > 500 limit
    assert decision.route == "needs_attention" and "above_max_per_purchase" in decision.reasons


def test_hallucinated_price_lowers_confidence_and_flags_field(env):
    decision, purchase, _ = env(transcript="20 sacs engrais", extraction=good(price=45))
    assert decision.route == "needs_attention"
    assert decision.flagged_fields == ["unit_price"]
    assert purchase.extraction_confidence <= 0.6


def test_rejected_model_output_goes_to_manual_entry(env):
    decision, purchase, _ = env(error=ExtractionOutputError("schema_mismatch", "unit_price"))
    assert decision.route == "manual_entry"
    assert decision.reasons == ["extraction_failed:schema_mismatch"]
    assert purchase.processing_status == "ready_for_review"


def test_unexpected_error_never_leaves_purchase_processing(env):
    decision, purchase, _ = env(error=KeyError("boom"))
    assert decision.reasons == ["extraction_failed:unexpected_error"]
    assert purchase.processing_status == "ready_for_review"


def test_empty_transcript_goes_to_manual_entry(env):
    decision, _, _ = env(transcript="  ")
    assert decision.route == "manual_entry" and decision.reasons == ["empty_transcript"]
