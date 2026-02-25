from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.deps import get_db
from app.models.alert import Alert
from app.models.user import User
from app.services.pdf_report import simple_table_pdf

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/alerts.pdf")
def export_alerts_pdf(
    db: Session = Depends(get_db),
    _user: User = require_roles("director", "admin"),
):
    alerts = (
        db.execute(select(Alert).order_by(Alert.created_at.desc()))
        .scalars()
        .all()
    )

    headers = ["Type", "Severity", "Status", "Purchase", "Date"]
    rows = [
        [
            a.alert_type,
            a.severity,
            a.status,
            str(a.purchase_id)[:8],
            a.created_at.date().isoformat(),
        ]
        for a in alerts
    ]

    pdf_bytes = simple_table_pdf("Alerts Report", headers, rows)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="alerts.pdf"'},
    )
