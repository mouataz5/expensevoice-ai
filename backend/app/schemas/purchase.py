import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PurchaseCreate(BaseModel):
    product_name: str
    category: Optional[str] = None
    quantity: int = Field(default=1, ge=1)
    unit_price: float = Field(default=0, ge=0)
    purchase_date: Optional[datetime] = None


class PurchaseOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    product_name: str
    category: Optional[str] = None
    quantity: int
    unit_price: float
    total_amount: float
    status: str
    purchase_date: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class PurchaseConfirm(BaseModel):
    product_name: str
    category: Optional[str] = None
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0)
    total_amount: float = Field(ge=0)
