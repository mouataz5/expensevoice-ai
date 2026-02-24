from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.deps import get_db
from app.models.purchase import Purchase
from app.models.user import User
from app.services.audit import audit_log
from app.services.llm_extract import extract_purchase_fields

router = APIRouter(prefix="/api/purchases", tags=["llm-extraction"])


@router.post("/{purchase_id}/extract")
async def extract_from_transcription(
    purchase_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    purchase = db.execute(
        select(Purchase).where(Purchase.id == purchase_id)
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

    extracted = await extract_purchase_fields(purchase.transcription)

    purchase.product_name = extracted.product_name
    purchase.category = extracted.category
    purchase.quantity = extracted.quantity
    purchase.unit_price = float(extracted.unit_price)
    purchase.total_amount = float(extracted.total_amount)
    purchase.status = "pending"

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
            "confidence": getattr(extracted, "confidence", None),
            "category": extracted.category,
        },
    )

    return {
        "purchase_id": str(purchase.id),
        "extracted": extracted.model_dump(),
        "status": purchase.status,
    }
