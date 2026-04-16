from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import USERS_READ, USERS_WRITE, require_permission
from app.core.security import hash_password
from app.db.deps import get_db
from app.models.user import User
from app.schemas.user import ResetPasswordIn, UserCreate, UserMapItem, UserOut, UserUpdate

router = APIRouter(prefix="", tags=["users"])  # routes: /admin/users, /dashboard/users-map


@router.get("/admin/users", response_model=list[UserOut])
def list_users_admin(
    db: Session = Depends(get_db),
    _user: User = require_permission(USERS_READ),
):
    """Admin: list all users (for User Management page)."""
    users = (
        db.execute(
            select(User).where(User.is_deleted == False).order_by(User.email.asc())
        )
        .scalars()
        .all()
    )
    return users


@router.post("/admin/users", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _user: User = require_permission(USERS_WRITE),
):
    """Admin: create a new user (email, password, role)."""
    existing = db.execute(
        select(User).where(User.email == payload.email, User.is_deleted == False)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")
    if payload.role not in ("employee", "director", "accountant", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role")
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/admin/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _user: User = require_permission(USERS_WRITE),
):
    """Admin: update user role and/or is_active."""
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.role is not None:
        if payload.role not in ("employee", "director", "accountant", "admin"):
            raise HTTPException(status_code=400, detail="Invalid role")
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/admin/users/{user_id}/reset-password")
def reset_user_password(
    user_id: UUID,
    payload: ResetPasswordIn,
    db: Session = Depends(get_db),
    _user: User = require_permission(USERS_WRITE),
):
    """Admin: set a new password for a user."""
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    return {"ok": True}


@router.get("/dashboard/users-map", response_model=list[UserMapItem])
def users_map(
    db: Session = Depends(get_db),
    _user: User = require_permission(USERS_READ),
):
    users = (
        db.execute(
            select(User).where(User.is_active == True, User.is_deleted == False).order_by(User.email.asc())
        )
        .scalars()
        .all()
    )
    return [
        UserMapItem(id=str(u.id), email=u.email, role=u.role)
        for u in users
    ]
