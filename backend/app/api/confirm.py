from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import PURCHASES_READ_ALL, require_permission
from app.core.rate_limit import limiter
from app.db.deps import get_db
from app.models.purchase import Purchase
from app.models.policy import Policy
from app.models.user import User
from app.schemas.purchase import PurchaseConfirm
from app.services.audit import audit_log
from app.agent.approval import approval_requirement
from app.services.rules import _get_policy, evaluate_rules_and_create_alerts, get_allowed_categories

router = APIRouter(prefix="/purchases", tags=["confirm"])


def _approval_workflow(db: Session) -> dict:
    p = db.execute(
        select(Policy).where(Policy.policy_type == "approval_workflow", Policy.is_active == True)  # noqa: E712
    ).scalar_one_or_none()
    return p.rule if p and isinstance(p.rule, dict) else {}


@router.post("/{purchase_id}/confirm")
@limiter.limit("30/minute")
def confirm_purchase(
    request: Request,
    purchase_id: UUID,
    payload: PurchaseConfirm,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Employee submits purchase for admin approval (status=pending_approval)."""
    purchase = db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    ).scalar_one_or_none()

    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    if user.role == "employee" and purchase.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    qty = int(payload.quantity)
    unit = float(payload.unit_price)
    if qty <= 0:
        raise HTTPException(status_code=422, detail="quantity must be >= 1")
    if unit < 0:
        raise HTTPException(status_code=422, detail="unit_price must be >= 0")

    allowed = get_allowed_categories(db)
    if payload.category is not None and allowed and payload.category not in allowed:
        raise HTTPException(status_code=422, detail="category not allowed by policy")

    server_total = round(qty * unit, 3)

    purchase.product_name = payload.product_name
    purchase.category = payload.category
    purchase.quantity = qty
    purchase.unit_price = unit
    purchase.total_amount = server_total
    # A director may switch manager approval off for routine purchases, but a
    # purchase that breaks a spending rule still goes to a manager.
    requirement = approval_requirement(
        workflow_rule=_approval_workflow(db),
        limits_rule=_get_policy(db, "limits"),
        total_amount=server_total,
        from_voice=bool(purchase.transcription),
        extraction_confidence=(
            float(purchase.extraction_confidence) if purchase.extraction_confidence is not None else None
        ),
    )
    purchase.status = "pending_approval" if requirement.requires_approval else "approved"
    if getattr(purchase, "processing_status", None):
        purchase.processing_status = "confirmed"

    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    audit_log(
        db,
        user=user,
        action="purchase_submitted",
        entity_type="purchase",
        entity_id=str(purchase.id),
        message=(
            "Purchase submitted for admin approval"
            if requirement.requires_approval
            else "Routine purchase auto-approved by policy"
        ),
        metadata={
            "total_amount": float(purchase.total_amount),
            "category": purchase.category,
            "product_name": purchase.product_name,
            "approval_reasons": requirement.reasons,
        },
    )

    alerts = evaluate_rules_and_create_alerts(db, purchase)

    return {
        "purchase_id": str(purchase.id),
        "status": purchase.status,
        "total_amount": float(purchase.total_amount),
        "approval_reasons": requirement.reasons,
        "alerts_created": [
            {"type": a.alert_type, "severity": a.severity, "message": a.message}
            for a in alerts
        ],
    }


@router.post("/{purchase_id}/approve")
@limiter.limit("30/minute")
def approve_purchase(
    request: Request,
    purchase_id: UUID,
    db: Session = Depends(get_db),
    user: User = require_permission(PURCHASES_READ_ALL),
):
    """Admin/director approves a pending purchase."""
    purchase = db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    ).scalar_one_or_none()

    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    if purchase.status not in ("pending_approval", "pending"):
        raise HTTPException(status_code=409, detail=f"Cannot approve purchase with status '{purchase.status}'")

    purchase.status = "approved"
    if getattr(purchase, "processing_status", None):
        purchase.processing_status = "approved"

    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    audit_log(
        db,
        user=user,
        action="purchase_approved",
        entity_type="purchase",
        entity_id=str(purchase.id),
        message=f"Purchase approved by {user.email}",
        metadata={
            "total_amount": float(purchase.total_amount),
            "approved_by": str(user.id),
        },
    )

    return {
        "purchase_id": str(purchase.id),
        "status": purchase.status,
        "total_amount": float(purchase.total_amount),
    }


@router.post("/{purchase_id}/reject")
@limiter.limit("30/minute")
def reject_purchase(
    request: Request,
    purchase_id: UUID,
    db: Session = Depends(get_db),
    user: User = require_permission(PURCHASES_READ_ALL),
):
    """Admin/director rejects a pending purchase."""
    purchase = db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    ).scalar_one_or_none()

    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    if purchase.status not in ("pending_approval", "pending"):
        raise HTTPException(status_code=409, detail=f"Cannot reject purchase with status '{purchase.status}'")

    purchase.status = "rejected"
    if getattr(purchase, "processing_status", None):
        purchase.processing_status = "rejected"

    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    audit_log(
        db,
        user=user,
        action="purchase_rejected",
        entity_type="purchase",
        entity_id=str(purchase.id),
        message=f"Purchase rejected by {user.email}",
        metadata={
            "total_amount": float(purchase.total_amount),
            "rejected_by": str(user.id),
        },
    )

    return {
        "purchase_id": str(purchase.id),
        "status": purchase.status,
    }
