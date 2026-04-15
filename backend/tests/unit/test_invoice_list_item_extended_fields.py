from datetime import datetime
from uuid import uuid4

from app.models.invoice import Invoice
from app.schemas.invoice import invoice_to_list_item


def test_invoice_list_item_contains_extended_filter_fields():
    inv = Invoice(
        id=uuid4(),
        user_id=uuid4(),
        transaction_type="buy",
        image_path="storage/invoices/test.jpg",
        extracted_json={"totals": {"htva": 100.0, "tva": 19.0, "ttc": 119.0}},
        invoice_number="INV-1",
        supplier_name="ACME",
        total_ttc=119.0,
        status="ready",
        created_at=datetime.utcnow(),
    )
    out = invoice_to_list_item(inv, "user@example.com")
    assert out["source"] == "scan"
    assert out["transaction_type"] == "buy"
    assert out["total_ht"] == 100.0
    assert out["total_tva"] == 19.0
    assert out["total_ttc"] == 119.0
