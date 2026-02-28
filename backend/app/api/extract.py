from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.db.deps import get_db
from app.models.purchase import Purchase
from app.models.user import User
from app.services.audit import audit_log
from app.services.extraction import extract_purchase_fields, validate_and_sanitize
from app.services.rules import get_allowed_categories

router = APIRouter(prefix="/purchases", tags=["llm-extraction"])


@router.post("/{purchase_id}/extract")
@limiter.limit("20/minute")
async def extract_from_transcription(
    request: Request,
    purchase_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Part 2: Extract with transaction_type; structured validation; server-side total."""
    purchase = db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    ).scalar_one_or_none()

    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    if user.role == "employee" and purchase.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if not purchase.transcription:
        raise HTTPException(
            status_code=400,
            detail="No transcription found on this purchase",
        )

    extracted = await extract_purchase_fields(
        purchase.transcription,
        transaction_type=purchase.transaction_type,
    )

    allowed = get_allowed_categories(db)
    qty, price, total, ext_conf = validate_and_sanitize(extracted, allowed)

    purchase.product_name = extracted.product_name or "(from_voice)"
    purchase.category = extracted.category
    purchase.quantity = qty
    purchase.unit_price = price
    purchase.total_amount = total
    purchase.extraction_confidence = float(ext_conf)
    purchase.status = "pending"
    if purchase.processing_status == "processing":
        purchase.processing_status = "ready_for_review"

    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    audit_log(
        db,
        user=user,
        action="purchase_extract",
        entity_type="purchase",
        entity_id=str(purchase.id),
        message="Purchase fields extracted from transcription",
        metadata={
            "confidence": ext_conf,
            "category": extracted.category,
        },
    )

    return {
        "purchase_id": str(purchase.id),
        "extracted": extracted.model_dump(),
        "status": purchase.status,
        "extraction_confidence": ext_conf,
    }
