from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


def audit_log(
    db: Session,
    *,
    user: User,
    action: str,
    entity_type: str,
    entity_id: str,
    message: str = "",
    metadata: dict | None = None,
):
    row = AuditLog(
        actor_user_id=user.id,
        actor_role=user.role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message or "",
        metadata_=metadata or {},
    )
    db.add(row)
    db.commit()
