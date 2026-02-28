"""
Settings API — GET (director/admin) and PUT (admin) for app settings.
Stored in database: company name, currency, logo URL, default limits, working days.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import SETTINGS_READ, SETTINGS_WRITE, require_permission
from app.db.deps import get_db
from app.models.setting import Setting
from app.models.user import User
from app.schemas.setting import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


def _get_settings_row(db: Session) -> Setting | None:
    return db.execute(select(Setting).limit(1)).scalar_one_or_none()


@router.get("", response_model=SettingsOut)
def get_settings(
    db: Session = Depends(get_db),
    _user: User = require_permission(SETTINGS_READ),
):
    """Get app settings (company name, currency, logo, default limits, working days)."""
    row = _get_settings_row(db)
    if not row:
        raise HTTPException(status_code=404, detail="Settings not found")
    return SettingsOut(
        company_name=row.company_name,
        currency=row.currency,
        logo_url=row.logo_url,
        default_limits=row.default_limits or {},
        working_days=row.working_days or [],
    )


@router.put("", response_model=SettingsOut)
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    _user: User = require_permission(SETTINGS_WRITE),
):
    """Update app settings (admin only)."""
    row = _get_settings_row(db)
    if not row:
        raise HTTPException(status_code=404, detail="Settings not found")
    if payload.company_name is not None:
        row.company_name = payload.company_name
    if payload.currency is not None:
        row.currency = payload.currency
    if payload.logo_url is not None:
        row.logo_url = payload.logo_url
    if payload.default_limits is not None:
        row.default_limits = payload.default_limits
    if payload.working_days is not None:
        row.working_days = payload.working_days
    db.add(row)
    db.commit()
    db.refresh(row)
    return SettingsOut(
        company_name=row.company_name,
        currency=row.currency,
        logo_url=row.logo_url,
        default_limits=row.default_limits or {},
        working_days=row.working_days or [],
    )
