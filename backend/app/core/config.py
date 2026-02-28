import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./expensevoice.db",
)
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key-change-later")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

# CORS: comma-separated origins for production; empty = use regex (localhost only)
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS_STR.split(",") if o.strip()]

# Audio upload: max size (bytes), retention days for cleanup (0 = no auto-delete)
MAX_AUDIO_BYTES = int(os.getenv("MAX_AUDIO_BYTES", str(10 * 1024 * 1024)))  # 10MB
AUDIO_RETENTION_DAYS = int(os.getenv("AUDIO_RETENTION_DAYS", "90"))

# Part 3.3: Redis for rate limiting (optional; if set, slowapi uses Redis backend)
REDIS_URL = os.getenv("REDIS_URL", "").strip() or None

# Part 3: App version for health endpoint
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
