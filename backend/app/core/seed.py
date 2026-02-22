import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User


def seed_user_if_not_exists(db: Session, email: str, password: str, role: str):
    existing = db.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()

    if existing:
        return

    user = User(
        email=email,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()


def seed_admin(db: Session):
    email = os.getenv("SEED_ADMIN_EMAIL")
    password = os.getenv("SEED_ADMIN_PASSWORD")
    role = os.getenv("SEED_ADMIN_ROLE", "admin")

    if email and password:
        seed_user_if_not_exists(db, email, password, role)


def seed_director(db: Session):
    email = os.getenv("SEED_DIRECTOR_EMAIL")
    password = os.getenv("SEED_DIRECTOR_PASSWORD")
    role = os.getenv("SEED_DIRECTOR_ROLE", "director")

    if email and password:
        seed_user_if_not_exists(db, email, password, role)
