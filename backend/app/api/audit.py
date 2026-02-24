from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.deps import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditOut

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditOut])
def list_audit(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("director", "admin")),
    actor_user_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=500),
):
    filters = []

    if actor_user_id:
        try:
            uid = UUID(actor_user_id)
            filters.append(AuditLog.actor_user_id == uid)
        except ValueError:
            pass
    if action:
        filters.append(AuditLog.action == action)
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)

    if date_from:
        start_dt = datetime(
            date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc
        )
        filters.append(AuditLog.created_at >= start_dt)
    if date_to:
        end_dt = datetime(
            date_to.year, date_to.month, date_to.day, tzinfo=timezone.utc
        ) + timedelta(days=1)
        filters.append(AuditLog.created_at < end_dt)

    q = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
    if filters:
        q = q.where(and_(*filters))

    rows = db.execute(q).scalars().all()
    return rows


@router.get("/me", response_model=list[AuditOut])
def my_audit(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=200),
):
    rows = (
        db.execute(
            select(AuditLog)
            .where(AuditLog.actor_user_id == user.id)
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return rows
