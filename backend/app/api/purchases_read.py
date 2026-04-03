from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.deps import get_db
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.purchase import PurchaseOut

router = APIRouter(prefix="/purchases", tags=["purchases-read"])


@router.get("/{purchase_id}", response_model=PurchaseOut)
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

    return p
