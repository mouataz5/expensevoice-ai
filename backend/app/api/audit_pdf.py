from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.deps import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.pdf_report import simple_table_pdf

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/audit.pdf")
def export_audit_pdf(
    db: Session = Depends(get_db),
    _user: User = require_roles("director", "admin"),
):
    rows_db = (
        db.execute(select(AuditLog).order_by(desc(AuditLog.created_at)))
        .scalars()
        .all()
    )

    headers = ["Action", "Role", "Entity", "Id", "Date"]
    rows = [
        [
            r.action,
            r.actor_role,
            r.entity_type,
            str(r.entity_id)[:8],
            r.created_at.date().isoformat(),
        ]
        for r in rows_db
    ]

    pdf_bytes = simple_table_pdf("Audit Report", headers, rows)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="audit.pdf"'},
    )
