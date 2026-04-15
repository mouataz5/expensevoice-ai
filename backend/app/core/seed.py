import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policy_defaults import (
    get_default_categories_policy,
    get_default_limits_policy,
)
from app.core.security import hash_password
from app.models.farm import Farm
from app.models.policy import Policy
from app.models.farm import Farm
from app.models.setting import Setting
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


def seed_settings(db: Session):
    """Create default app settings row if none exists."""
    existing = db.execute(select(Setting)).first()
    if existing:
        return
    defaults = get_default_limits_policy()
    db.add(
        Setting(
            company_name="نظام عبّاس لإدارة الضيعة",
            currency="TND",
            logo_url=None,
            default_limits=defaults,
            working_days=[0, 1, 2, 3, 4],  # Mon–Fri (ISO)
        )
    )
    db.commit()


def seed_farms(db: Session):
    """Create default farms when none exist."""
    existing = db.execute(select(Farm)).scalars().first()
    if existing:
        return
    defaults = [
        "Farm 1",
        "Farm 2",
        "Farm 3",
        "Farm 4",
    ]
    for name in defaults:
        db.add(Farm(name=name, is_active=True))
    db.commit()


def seed_farms(db: Session):
    """Seed a default list of farms if missing."""
    raw = os.getenv("SEED_FARM_NAMES", "Farm 1,Farm 2,Farm 3")
    names = [name.strip() for name in raw.split(",") if name.strip()]
    if not names:
        names = ["Farm 1"]
    existing = db.execute(select(Farm.name)).all()
    existing_names = {row[0] for row in existing}
    created = False
    for name in names:
        if name in existing_names:
            continue
        db.add(Farm(name=name, is_active=True))
        created = True
    if created:
        db.commit()
