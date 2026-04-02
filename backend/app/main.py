import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import router as v1_router
from app.core.config import APP_VERSION, CORS_ORIGINS
from app.core.logging_config import setup_structured_logging
from app.core.rate_limit import limiter
from app.core.seed import seed_admin, seed_director, seed_employee, seed_policies, seed_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.middlewares.request_logging import RequestLoggingMiddleware
from app.middlewares.security_headers import SecurityHeadersMiddleware
from app.models.alert import Alert  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.invoice import Invoice  # noqa: F401
from app.models.policy import Policy  # noqa: F401
from app.models.purchase import Purchase  # noqa: F401
from app.models.setting import Setting  # noqa: F401
from app.models.user import User  # noqa: F401

# Part 3.2: Structured logging (JSON in production)
_json_logs = os.getenv("JSON_LOGS", "true").strip().lower() in ("1", "true", "yes")
setup_structured_logging(json_logs=_json_logs)

app = FastAPI(title="ExpenseVoice AI API", version=APP_VERSION)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

    # Add is_active to users if table existed before (migration)
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            if "postgresql" in str(engine.url):
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true NOT NULL"))
            elif "sqlite" in str(engine.url):
                # SQLite doesn't support IF NOT EXISTS for columns; ignore if already exists
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"))
                except Exception:
                    pass
            conn.commit()
            # Soft delete columns (Part 2.1)
            for table, col in [("users", "is_deleted"), ("purchases", "is_deleted"), ("alerts", "is_deleted")]:
                try:
                    if "postgresql" in str(engine.url):
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} BOOLEAN DEFAULT false NOT NULL"))
                    elif "sqlite" in str(engine.url):
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} BOOLEAN DEFAULT 0"))
                    conn.commit()
                except Exception:
                    pass
            # Voice pipeline: transaction_type, processing_status, stt_confidence, extraction_confidence
            for col in ["transaction_type", "processing_status", "stt_confidence", "extraction_confidence"]:
                try:
                    if "postgresql" in str(engine.url):
                        if col in ("stt_confidence", "extraction_confidence"):
                            conn.execute(text(f"ALTER TABLE purchases ADD COLUMN IF NOT EXISTS {col} NUMERIC(5,4)"))
                        elif col == "processing_status":
                            conn.execute(text("ALTER TABLE purchases ADD COLUMN IF NOT EXISTS processing_status VARCHAR(30) DEFAULT 'processing'"))
                        else:
                            conn.execute(text(f"ALTER TABLE purchases ADD COLUMN IF NOT EXISTS {col} VARCHAR(30)"))
                    elif "sqlite" in str(engine.url):
                        conn.execute(text(f"ALTER TABLE purchases ADD COLUMN {col}"))
                    conn.commit()
                except Exception:
                    pass
            # Invoice: pdf_path, denormalized list fields
            if "postgresql" in str(engine.url):
                for col, col_type in [
                    ("pdf_path", "VARCHAR(500)"),
                    ("invoice_number", "VARCHAR(100)"),
                    ("supplier_name", "VARCHAR(255)"),
                    ("total_ttc", "NUMERIC(14,3)"),
                    ("corrected_json", "JSONB"),
                ]:
                    try:
                        conn.execute(text(f"ALTER TABLE invoices ADD COLUMN IF NOT EXISTS {col} {col_type}"))
                        conn.commit()
                    except Exception:
                        pass
            elif "sqlite" in str(engine.url):
                for col, col_type in [
                    ("pdf_path", "VARCHAR(500)"),
                    ("invoice_number", "VARCHAR(100)"),
                    ("supplier_name", "VARCHAR(255)"),
                    ("total_ttc", "REAL"),
                    ("corrected_json", "TEXT"),
                ]:
                    try:
                        conn.execute(text(f"ALTER TABLE invoices ADD COLUMN {col} {col_type}"))
                        conn.commit()
                    except Exception:
                        pass
    except Exception:
        pass

    db = SessionLocal()
    try:
        seed_admin(db)
        seed_director(db)
        seed_employee(db)
        seed_policies(db)
        seed_settings(db)
    finally:
        db.close()


# Part 2.2: All API routes under /api/v1
app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
def health():
    """
    Part 3.1: Health check for load balancers / k8s.
    Returns status, database connectivity, and version.
    """
    from sqlalchemy import text

    payload = {
        "status": "ok",
        "version": APP_VERSION,
    }
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        payload["database"] = "ok"
    except Exception as e:
        payload["database"] = "error"
        payload["database_error"] = str(e)
        payload["status"] = "degraded"
    return payload
