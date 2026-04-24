from datetime import datetime

from pydantic import BaseModel, Field


class FarmCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class FarmOut(BaseModel):
    id: str
    name: str
    is_active: bool
    created_at: datetime
