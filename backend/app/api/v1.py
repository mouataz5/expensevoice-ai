"""
API v1 router — all routes are mounted under /api/v1.
Part 2.2: Versioned API.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.api.audit import router as audit_router
from app.api.audit_export import router as audit_export_router
from app.api.audit_pdf import router as audit_pdf_router
from app.api.alerts import router as alerts_router
from app.api.alerts_export import router as alerts_export_router
from app.api.alerts_pdf import router as alerts_pdf_router
from app.api.stats_pdf import router as stats_pdf_router
from app.api.auth import router as auth_router
from app.api.confirm import router as confirm_router
from app.api.dashboard import router as dashboard_router
from app.api.extract import router as extract_router
from app.api.policies import router as policies_router
from app.api.policies_public import router as policies_public_router
from app.api.policies_read import router as policies_read_router
from app.api.purchase_alerts import router as purchase_alerts_router
from app.api.purchases import router as purchases_router
from app.api.purchases_read import router as purchases_read_router
from app.api.users import router as users_router
from app.api.voice import router as voice_router
from app.api.settings import router as settings_router
from app.api.invoices import router as invoices_router
from app.api.speech import router as speech_router
from app.core.config import APP_VERSION
from app.core.dependencies import get_current_user
from app.db.session import engine
from app.models.user import User

# Single v1 router: prefix is applied in main as /api/v1
router = APIRouter()


@router.get("/health")
def health_v1():
    """Alias versionné de GET /health (load balancer / spec API v1)."""
    payload = {"status": "ok", "version": APP_VERSION}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        payload["database"] = "ok"
    except Exception as e:
        payload["database"] = "error"
        payload["database_error"] = str(e)
        payload["status"] = "degraded"
    return payload

# Auth & me
router.include_router(auth_router)
router.include_router(users_router)

# Purchases (multiple routers under /purchases)
router.include_router(purchases_router)
router.include_router(voice_router)
router.include_router(purchase_alerts_router)
router.include_router(purchases_read_router)
router.include_router(extract_router)
router.include_router(confirm_router)

# Dashboard, Alerts, Audit
router.include_router(dashboard_router)
router.include_router(alerts_router)
router.include_router(audit_router)

# Export (CSV/PDF)
router.include_router(alerts_export_router)
router.include_router(alerts_pdf_router)
router.include_router(audit_export_router)
router.include_router(audit_pdf_router)
router.include_router(stats_pdf_router)

# Policies & Settings
router.include_router(policies_router)
router.include_router(policies_public_router)
router.include_router(policies_read_router)
router.include_router(settings_router)
router.include_router(invoices_router)
router.include_router(speech_router)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    """Current user info; part of v1 API."""
    return {"id": str(user.id), "email": user.email, "role": user.role}
