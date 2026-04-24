from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import USERS_WRITE, require_permission
from app.db.deps import get_db
from app.models.farm import Farm
from app.models.user import User
from app.schemas.farm import FarmCreate, FarmOut

router = APIRouter(prefix="/farms", tags=["farms"])


@router.get("", response_model=list[FarmOut])
def list_farms(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(Farm).where(Farm.is_active == True).order_by(Farm.name.asc())  # noqa: E712
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


@router.post("", response_model=FarmOut, status_code=status.HTTP_201_CREATED)
def create_farm(
    payload: FarmCreate,
    db: Session = Depends(get_db),
    _user: User = require_permission(USERS_WRITE),
):
    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Farm name must contain at least 2 characters")

    exists = db.execute(
        select(Farm).where(func.lower(Farm.name) == name.lower())
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Farm name already exists")

    farm = Farm(name=name, is_active=True)
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return FarmOut(
        id=str(farm.id),
        name=farm.name,
        is_active=bool(farm.is_active),
        created_at=farm.created_at,
    )
