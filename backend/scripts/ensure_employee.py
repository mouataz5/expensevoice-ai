"""
Create or reset the default employee user so you can log in.
Run from backend dir: python -m scripts.ensure_employee
Or: uv run python -m scripts.ensure_employee
"""
import os
import sys

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User

EMAIL = os.getenv("SEED_EMPLOYEE_EMAIL", "employee@company.com")
PASSWORD = os.getenv("SEED_EMPLOYEE_PASSWORD", "Employee12345!")


def main():
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == EMAIL)).scalar_one_or_none()
        if user:
            user.password_hash = hash_password(PASSWORD)
            user.role = "employee"
            db.add(user)
            db.commit()
            print(f"Employee updated: {EMAIL}")
        else:
            db.add(
                User(
                    email=EMAIL,
                    password_hash=hash_password(PASSWORD),
                    role="employee",
                )
            )
            db.commit()
            print(f"Employee created: {EMAIL}")
        print("Password:", PASSWORD)
    finally:
        db.close()


if __name__ == "__main__":
    main()
