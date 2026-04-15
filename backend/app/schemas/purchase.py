import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PurchaseCreate(BaseModel):
    farm_id: uuid.UUID | None = None
    product_name: str
    category: Optional[str] = None
    quantity: int = Field(default=1, ge=1)
    unit_price: float = Field(default=0, ge=0)
    purchase_date: Optional[datetime] = None


class PurchaseOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    farm_id: uuid.UUID | None = None
    farm_name: str | None = None
    product_name: str
    category: Optional[str] = None
    quantity: int
    unit_price: float
    total_amount: float
    status: str
    purchase_date: datetime
    created_at: datetime
    # Voix / pipeline (aligné mobile + GET détail)
    transaction_type: Optional[str] = None
    processing_status: Optional[str] = None
    stt_confidence: Optional[float] = None
    extraction_confidence: Optional[float] = None
    transcription: Optional[str] = None
    audio_file_path: Optional[str] = None
    source: Optional[str] = None
    total_ht: Optional[float] = None
    total_tva: Optional[float] = None
    total_ttc: Optional[float] = None
    is_tax_estimated: Optional[bool] = None
    employee_email: Optional[str] = None

    model_config = {"from_attributes": True}


class PurchaseConfirm(BaseModel):
    product_name: str
    category: Optional[str] = None
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0)
    total_amount: float = Field(ge=0)
