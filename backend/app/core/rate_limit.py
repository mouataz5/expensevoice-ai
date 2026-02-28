from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import REDIS_URL

# Part 3.3: Use Redis for rate limiting when REDIS_URL is set (production).
# Otherwise in-memory store (single instance only).
_limiter_kwargs: dict = {"key_func": get_remote_address}
if REDIS_URL:
    _limiter_kwargs["storage_uri"] = REDIS_URL

limiter = Limiter(**_limiter_kwargs)
