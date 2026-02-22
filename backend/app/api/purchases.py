from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.deps import get_db
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.purchase import PurchaseCreate, PurchaseOut

router = APIRouter(prefix="/api/purchases", tags=["purchases"])


@router.post("", response_model=PurchaseOut)
def create_purchase(
    payload: PurchaseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    purchase_date = payload.purchase_date or datetime.utcnow()
    total = float(payload.quantity) * float(payload.unit_price)

    item = Purchase(
        user_id=user.id,
        product_name=payload.product_name,
        category=payload.category,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        total_amount=total,
        purchase_date=purchase_date,
        status="approved",
    )

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/me", response_model=list[PurchaseOut])
def list_my_purchases(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.execute(
            select(Purchase)
            .where(Purchase.user_id == user.id)
            .order_by(Purchase.created_at.desc())
        )
        .scalars()
        .all()
    )
    return rows


@router.get("/all", response_model=list[PurchaseOut])
def list_all_purchases(
    db: Session = Depends(get_db),
    _user: User = require_roles("director", "admin"),
):
    rows = (
        db.execute(
            select(Purchase).order_by(Purchase.created_at.desc())
        )
        .scalars()
        .all()
    )
    return rows
