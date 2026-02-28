from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.db.deps import get_db
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.purchase import PurchaseConfirm
from app.services.audit import audit_log
from app.services.rules import evaluate_rules_and_create_alerts, get_allowed_categories

router = APIRouter(prefix="/purchases", tags=["confirm"])


@router.post("/{purchase_id}/confirm")
@limiter.limit("30/minute")
def confirm_purchase(
    request: Request,
    purchase_id: UUID,
    payload: PurchaseConfirm,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    purchase = db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    ).scalar_one_or_none()

    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    if user.role == "employee" and purchase.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Server-side validation: ignore client total_amount
    qty = int(payload.quantity)
    unit = float(payload.unit_price)
    if qty <= 0:
        raise HTTPException(status_code=422, detail="quantity must be >= 1")
    if unit < 0:
        raise HTTPException(status_code=422, detail="unit_price must be >= 0")

    allowed = get_allowed_categories(db)
    if payload.category is not None and allowed and payload.category not in allowed:
        raise HTTPException(status_code=422, detail="category not allowed by policy")

    # Server-side truth: never trust client total_amount
    server_total = round(qty * unit, 3)

    purchase.product_name = payload.product_name
    purchase.category = payload.category
    purchase.quantity = qty
    purchase.unit_price = unit
    purchase.total_amount = server_total
    purchase.status = "approved"
    if getattr(purchase, "processing_status", None):
        purchase.processing_status = "approved"

    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    audit_log(
        db,
        user=user,
        action="purchase_confirm",
        entity_type="purchase",
        entity_id=str(purchase.id),
        message="Purchase confirmed",
        metadata={
            "total_amount": float(purchase.total_amount),
            "category": purchase.category,
            "product_name": purchase.product_name,
        },
    )

    alerts = evaluate_rules_and_create_alerts(db, purchase)

    return {
        "purchase_id": str(purchase.id),
        "status": purchase.status,
        "total_amount": float(purchase.total_amount),
        "alerts_created": [
            {"type": a.alert_type, "severity": a.severity, "message": a.message}
            for a in alerts
        ],
    }
