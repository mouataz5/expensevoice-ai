from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.deps import get_db
from app.models.policy import Policy
from app.models.user import User
from app.schemas.policy import PolicyOut

router = APIRouter(prefix="/api/policies", tags=["policies-read"])


@router.get("/active", response_model=list[PolicyOut])
def list_active_policies(
    db: Session = Depends(get_db),
    _user: User = require_roles("director", "admin"),
):
    rows = (
        db.execute(
            select(Policy)
            .where(Policy.is_active.is_(True))
            .order_by(Policy.policy_type.asc())
        )
        .scalars()
        .all()
    )
    return rows


@router.get("/{policy_type}", response_model=PolicyOut)
def get_policy_readonly(
    policy_type: str,
    db: Session = Depends(get_db),
    _user: User = require_roles("director", "admin"),
):
    p = db.execute(
        select(Policy).where(Policy.policy_type == policy_type)
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Policy not found")
    return p
