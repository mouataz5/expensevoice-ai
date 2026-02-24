from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.deps import get_db
from app.models.policy import Policy
from app.models.user import User
from app.schemas.policy import (
    CategoriesRule,
    LimitsRule,
    PolicyOut,
    PolicyUpdate,
)
from app.services.audit import audit_log

router = APIRouter(prefix="/api/admin/policies", tags=["policies-admin"])


@router.get("", response_model=list[PolicyOut])
def list_policies(
    db: Session = Depends(get_db),
    _user: User = require_roles("admin"),
):
    rows = (
        db.execute(select(Policy).order_by(Policy.policy_type.asc()))
        .scalars()
        .all()
    )
    return rows


@router.get("/{policy_type}", response_model=PolicyOut)
def get_policy(
    policy_type: str,
    db: Session = Depends(get_db),
    _user: User = require_roles("admin"),
):
    p = db.execute(
        select(Policy).where(Policy.policy_type == policy_type)
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Policy not found")
    return p


@router.put("/{policy_type}", response_model=PolicyOut)
def update_policy(
    policy_type: str,
    payload: PolicyUpdate,
    db: Session = Depends(get_db),
    _user: User = require_roles("admin"),
):
    p = db.execute(
        select(Policy).where(Policy.policy_type == policy_type)
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Policy not found")

    if policy_type == "limits":
        validated = LimitsRule(**payload.rule).model_dump()
        p.rule = validated
    elif policy_type == "categories":
        validated = CategoriesRule(**payload.rule).model_dump()
        p.rule = validated
    else:
        raise HTTPException(
            status_code=400, detail="Unsupported policy_type"
        )

    if payload.is_active is not None:
        p.is_active = payload.is_active

    db.add(p)
    db.commit()
    db.refresh(p)

    audit_log(
        db,
        user=_user,
        action="policy_update",
        entity_type="policy",
        entity_id=str(p.id),
        message=f"Policy '{policy_type}' updated",
        metadata={
            "policy_type": policy_type,
            "is_active": p.is_active,
            "rule": p.rule,
        },
    )

    return p
