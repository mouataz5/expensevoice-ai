import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User


def seed_admin(db: Session):
    email = os.getenv("SEED_ADMIN_EMAIL")
    password = os.getenv("SEED_ADMIN_PASSWORD")
    role = os.getenv("SEED_ADMIN_ROLE", "admin")

    if not email or not password:
        return

    existing_admin = db.execute(
        select(User).where(User.role == "admin")
    ).scalar_one_or_none()

    if existing_admin:
        return

    admin = User(
        email=email,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(admin)
    db.commit()
