from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"), password_hash.encode("utf-8")
    )


def create_access_token(subject: str, secret_key: str, expires_minutes: int):
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expires_minutes)

    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": exp,
    }

    return jwt.encode(payload, secret_key, algorithm="HS256")
