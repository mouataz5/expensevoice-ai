from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_SECRET
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.deps import get_db
from app.models.user import User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
@limiter.limit("5/minute")
def register(
    request: Request,
    payload: RegisterIn,
    db: Session = Depends(get_db),
):
    existing = db.execute(
        select(User).where(User.email == payload.email, User.is_deleted == False)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    if payload.role not in ["employee", "director", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        subject=str(user.id),
        secret_key=JWT_SECRET,
        expires_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
    )

    return TokenOut(access_token=token)


@router.post("/login", response_model=TokenOut)
@limiter.limit("10/minute")
def login(
    request: Request,
    payload: LoginIn,
    db: Session = Depends(get_db),
):
    user = db.execute(
        select(User).where(User.email == payload.email, User.is_deleted == False)
    ).scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not getattr(user, "is_active", True):
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token(
        subject=str(user.id),
        secret_key=JWT_SECRET,
        expires_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
    )

    return TokenOut(access_token=token)
