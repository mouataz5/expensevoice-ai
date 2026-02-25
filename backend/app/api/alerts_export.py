import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.deps import get_db
from app.models.alert import Alert
from app.models.user import User

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/alerts.csv")
def export_alerts_csv(
    db: Session = Depends(get_db),
    _user: User = require_roles("director", "admin"),
):
    alerts = (
        db.execute(select(Alert).order_by(Alert.created_at.desc()))
        .scalars()
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "purchase_id",
            "alert_type",
            "severity",
            "status",
            "message",
            "created_at",
        ]
    )

    for a in alerts:
        writer.writerow(
            [
                str(a.id),
                str(a.purchase_id),
                a.alert_type,
                a.severity,
                a.status,
                a.message,
                a.created_at.isoformat(),
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="alerts.csv"'},
    )
