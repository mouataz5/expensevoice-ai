from datetime import datetime
from uuid import uuid4

from app.api.purchases import _purchase_to_out, _purchase_totals
from app.models.purchase import Purchase


def _sample_purchase(total_amount: float = 119.0, audio_file_path: str | None = None) -> Purchase:
    return Purchase(
        id=uuid4(),
        user_id=uuid4(),
        product_name="Sample",
        category="autre",
        quantity=1,
        unit_price=total_amount,
        total_amount=total_amount,
        status="pending",
        transaction_type="buy",
        processing_status="ready_for_review",
        audio_file_path=audio_file_path,
        created_at=datetime.utcnow(),
        purchase_date=datetime.utcnow(),
    )


def test_purchase_totals_estimation_has_ht_tva_ttc():
    purchase = _sample_purchase(119.0)
    ht, tva, ttc, estimated = _purchase_totals(purchase)
    assert round(ht + tva, 3) == round(ttc, 3)
    assert ttc == 119.0
    assert estimated is True


def test_purchase_to_out_infers_voice_source():
    purchase = _sample_purchase(50.0, audio_file_path="storage/audio/test.m4a")
    out = _purchase_to_out(purchase, employee_email="a@b.com")
    assert out["source"] == "voice"
    assert out["employee_email"] == "a@b.com"
    assert out["is_tax_estimated"] is True
    assert "total_ht" in out and "total_tva" in out and "total_ttc" in out
