from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.deps import get_db
from app.models.alert import Alert
from app.models.purchase import Purchase
from app.models.user import User

router = APIRouter(prefix="/api/purchases", tags=["purchase-alerts"])


@router.get("/{purchase_id}/alerts")
def alerts_for_purchase(
    purchase_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = db.execute(select(Purchase).where(Purchase.id == purchase_id)).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found")

    if user.role == "employee" and p.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    alerts = (
        db.execute(
            select(Alert)
            .where(Alert.purchase_id == p.id)
            .order_by(Alert.created_at.desc())
        )
        .scalars()
        .all()
    )

    return [
        {
            "id": str(a.id),
            "purchase_id": str(a.purchase_id),
            "alert_type": a.alert_type,
            "message": a.message,
            "severity": a.severity,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts
    ]
