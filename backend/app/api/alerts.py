from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import ALERTS_READ, ALERTS_RESOLVE, require_permission
from app.db.deps import get_db
from app.models.alert import Alert
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.alert import AlertOut
from app.services.audit import audit_log

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/notifications")
def get_notifications(
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    _user: User = require_permission(ALERTS_READ),
):
    """
    Returns count of unresolved critical alerts and latest N alerts for the notification center.
    """
    count_result = db.execute(
        select(func.count(Alert.id))
        .select_from(Alert)
        .where(
            Alert.is_deleted == False,
            Alert.status != "resolved",
            Alert.severity == "critical",
        )
    ).scalar_one()
    count = count_result or 0
    items = (
        db.execute(
            select(Alert)
            .where(Alert.is_deleted == False)
            .order_by(Alert.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return {
        "count": count,
        "items": [AlertOut.model_validate(a) for a in items],
    }


@router.get("", response_model=list[AlertOut])
def list_alerts(
    db: Session = Depends(get_db),
    _user: User = require_permission(ALERTS_READ),
):
    alerts = (
        db.execute(
            select(Alert).where(Alert.is_deleted == False).order_by(Alert.created_at.desc())
        )
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
            select(Purchase.id).where(Purchase.user_id == user.id, Purchase.is_deleted == False)
        ).all()
    ]
    if not purchase_ids:
        return []
    alerts = (
        db.execute(
            select(Alert)
            .where(Alert.purchase_id.in_(purchase_ids), Alert.is_deleted == False)
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
    _user: User = require_permission(ALERTS_RESOLVE),
):
    alert = db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.is_deleted == False)
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
