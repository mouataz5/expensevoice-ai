import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.deps import get_db
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/audit.csv")
def export_audit_csv(
    db: Session = Depends(get_db),
    _user: User = require_roles("director", "admin"),
):
    rows = (
        db.execute(select(AuditLog).order_by(desc(AuditLog.created_at)))
        .scalars()
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "actor_user_id",
            "actor_role",
            "action",
            "entity_type",
            "entity_id",
            "message",
            "created_at",
        ]
    )

    for r in rows:
        writer.writerow(
            [
                str(r.id),
                str(r.actor_user_id),
                r.actor_role,
                r.action,
                r.entity_type,
                r.entity_id,
                r.message,
                r.created_at.isoformat(),
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit.csv"'},
    )
