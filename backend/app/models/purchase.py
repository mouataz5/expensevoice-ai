import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    product_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="(from_voice)"
    )
    category: Mapped[str] = mapped_column(String(100), nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(
        Numeric(12, 3), nullable=False, default=0
    )
    total_amount: Mapped[float] = mapped_column(
        Numeric(12, 3), nullable=False, default=0
    )

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )  # approved/pending/rejected

    # Voice fields
    audio_file_path: Mapped[str] = mapped_column(String(500), nullable=True)
    transcription: Mapped[str] = mapped_column(Text, nullable=True)

    purchase_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
