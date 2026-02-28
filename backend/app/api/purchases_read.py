from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.deps import get_db
from app.models.purchase import Purchase
from app.models.user import User

router = APIRouter(prefix="/purchases", tags=["purchases-read"])


@router.get("/{purchase_id}")
def get_purchase(
    purchase_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found")

    if user.role == "employee" and p.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return {
        "id": str(p.id),
        "user_id": str(p.user_id),
        "product_name": p.product_name,
        "category": p.category,
        "quantity": p.quantity,
        "unit_price": float(p.unit_price),
        "total_amount": float(p.total_amount),
        "status": p.status,
        "transaction_type": getattr(p, "transaction_type", None),
        "processing_status": getattr(p, "processing_status", None),
        "stt_confidence": float(p.stt_confidence) if getattr(p, "stt_confidence", None) is not None else None,
        "extraction_confidence": float(p.extraction_confidence) if getattr(p, "extraction_confidence", None) is not None else None,
        "transcription": p.transcription,
        "audio_file_path": p.audio_file_path,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
