from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.deps import get_db
from app.models.purchase import Purchase
from app.models.user import User

router = APIRouter(prefix="/api/purchases", tags=["purchases-read"])


@router.get("/{purchase_id}")
def get_purchase(
    purchase_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = db.execute(select(Purchase).where(Purchase.id == purchase_id)).scalar_one_or_none()
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
        "transcription": p.transcription,
        "audio_file_path": p.audio_file_path,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
