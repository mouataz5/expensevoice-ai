import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    purchase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchases.id"), nullable=False
    )

    alert_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # e.g. "daily_limit"
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="warning"
    )  # info/warning/critical
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="new"
    )  # new/ack/resolved

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)
