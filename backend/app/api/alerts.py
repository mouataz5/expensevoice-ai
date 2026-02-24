from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.deps import get_db
from app.models.alert import Alert
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.alert import AlertOut
from app.services.audit import audit_log

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(
    db: Session = Depends(get_db),
    _user: User = require_roles("director", "admin"),
):
    alerts = (
        db.execute(select(Alert).order_by(Alert.created_at.desc()))
        .scalars()
        .all()
    )
    return alerts


@router.get("/me", response_model=list[AlertOut])
def my_alerts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role in ("director", "admin"):
        raise HTTPException(
            status_code=400, detail="Use /api/alerts"
        )
    purchase_ids = [
        row[0]
        for row in db.execute(
            select(Purchase.id).where(Purchase.user_id == user.id)
        ).all()
    ]
    if not purchase_ids:
        return []
    alerts = (
        db.execute(
            select(Alert)
            .where(Alert.purchase_id.in_(purchase_ids))
            .order_by(Alert.created_at.desc())
        )
        .scalars()
        .all()
    )
    return alerts


@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    _user: User = require_roles("director", "admin"),
):
    alert = db.execute(
        select(Alert).where(Alert.id == alert_id)
    ).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "resolved"
    db.add(alert)
    db.commit()

    audit_log(
        db,
        user=_user,
        action="alert_resolve",
        entity_type="alert",
        entity_id=str(alert.id),
        message="Alert resolved",
        metadata={
            "purchase_id": str(alert.purchase_id),
            "alert_type": alert.alert_type,
        },
    )

    return {"alert_id": str(alert.id), "status": alert.status}
