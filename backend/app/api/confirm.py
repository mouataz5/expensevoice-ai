from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.deps import get_db
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.purchase import PurchaseConfirm

router = APIRouter(prefix="/api/purchases", tags=["confirm"])


@router.post("/{purchase_id}/confirm")
def confirm_purchase(
    purchase_id: UUID,
    payload: PurchaseConfirm,
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

    purchase.product_name = payload.product_name
    purchase.category = payload.category
    purchase.quantity = payload.quantity
    purchase.unit_price = payload.unit_price
    purchase.total_amount = float(payload.quantity) * float(payload.unit_price)
    purchase.status = "approved"

    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    return {
        "purchase_id": str(purchase.id),
        "status": purchase.status,
        "total_amount": float(purchase.total_amount),
    }
