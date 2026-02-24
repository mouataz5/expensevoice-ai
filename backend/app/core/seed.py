import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policy_defaults import (
    get_default_categories_policy,
    get_default_limits_policy,
)
from app.core.security import hash_password
from app.models.policy import Policy
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
    email = os.getenv("SEED_ADMIN_EMAIL", "admin@company.com")
    password = os.getenv("SEED_ADMIN_PASSWORD", "Admin12345!")
    role = os.getenv("SEED_ADMIN_ROLE", "admin")

    if email and password:
        seed_user_if_not_exists(db, email, password, role)


def seed_director(db: Session):
    email = os.getenv("SEED_DIRECTOR_EMAIL", "director@company.com")
    password = os.getenv("SEED_DIRECTOR_PASSWORD", "Director12345!")
    role = os.getenv("SEED_DIRECTOR_ROLE", "director")

    if email and password:
        seed_user_if_not_exists(db, email, password, role)


def seed_employee(db: Session):
    email = os.getenv("SEED_EMPLOYEE_EMAIL", "employee@company.com")
    password = os.getenv("SEED_EMPLOYEE_PASSWORD", "Employee12345!")
    role = os.getenv("SEED_EMPLOYEE_ROLE", "employee")

    if email and password:
        seed_user_if_not_exists(db, email, password, role)


def seed_policies(db: Session):
    existing_limits = db.execute(
        select(Policy).where(Policy.policy_type == "limits")
    ).scalar_one_or_none()

    if not existing_limits:
        db.add(
            Policy(
                policy_type="limits",
                rule=get_default_limits_policy(),
                is_active=True,
            )
        )
        db.commit()

    existing_categories = db.execute(
        select(Policy).where(Policy.policy_type == "categories")
    ).scalar_one_or_none()

    if not existing_categories:
        db.add(
            Policy(
                policy_type="categories",
                rule=get_default_categories_policy(),
                is_active=True,
            )
        )
        db.commit()
