from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.deps import get_db
from app.models.farm import Farm
from app.models.user import User
from app.schemas.farm import FarmOut

router = APIRouter(prefix="/farms", tags=["farms"])


@router.get("", response_model=list[FarmOut])
def list_farms(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(Farm).where(Farm.is_active == True).order_by(Farm.name.asc())
    ).scalars().all()
    return [
        FarmOut(
            id=str(row.id),
            name=row.name,
            is_active=bool(row.is_active),
            created_at=row.created_at,
        )
        for row in rows
    ]
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.deps import get_db
from app.models.farm import Farm
from app.models.user import User

router = APIRouter(prefix="/farms", tags=["farms"])


@router.get("")
def list_farms(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(Farm).where(Farm.is_active == True).order_by(Farm.name.asc())  # noqa: E712
    ).scalars().all()
    return [{"id": str(f.id), "name": f.name, "is_active": bool(f.is_active)} for f in rows]
