"""
App settings — singleton row storing company name, currency, logo, default limits, working days.
Stored in database for production-level configuration.
"""
from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Singleton row id for app settings
SETTINGS_ROW_ID = 1


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, default="نظام عبّاس")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="TND")
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    # Default limits used when no policy override: max_per_purchase, daily_limit_default
    default_limits: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Working days: list of weekday numbers 0=Monday .. 6=Sunday (ISO), or empty = all days
    working_days: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
