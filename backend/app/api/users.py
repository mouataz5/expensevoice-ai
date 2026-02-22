from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.deps import get_db
from app.models.user import User
from app.schemas.user import UserMapItem, UserOut

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/admin/users", response_model=list[UserOut])
def list_users_admin(
    db: Session = Depends(get_db),
    _user: User = require_roles("admin"),
):
    users = (
        db.execute(select(User).order_by(User.email.asc()))
        .scalars()
        .all()
    )
    return users


@router.get("/dashboard/users-map", response_model=list[UserMapItem])
def users_map(
    db: Session = Depends(get_db),
    _user: User = require_roles("director", "admin"),
):
    users = (
        db.execute(select(User).order_by(User.email.asc()))
        .scalars()
        .all()
    )
    return [
        UserMapItem(id=str(u.id), email=u.email, role=u.role)
        for u in users
    ]
