import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)

    action: Mapped[str] = mapped_column(
        String(80), nullable=False
    )  # e.g. purchase_confirm, policy_update
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # purchase, policy, alert
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)

    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
