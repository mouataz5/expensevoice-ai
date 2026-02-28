"""
Invoice model — scanned invoices; PDF report is the user-facing output.
Stores image path, optional pdf_path, denormalized fields for list (no JSON exposed).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    transaction_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "buy" | "sell"
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # generated report PDF
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # internal only, not exposed

    # Denormalized for list display (no JSON exposure)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_ttc: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="processing"
    )  # processing | ready | failed | approved | rejected
    extraction_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)  # when status=failed
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)  # when status=rejected

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
