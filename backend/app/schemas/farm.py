from datetime import datetime

from pydantic import BaseModel


class FarmOut(BaseModel):
    id: str
    name: str
    is_active: bool
    created_at: datetime
