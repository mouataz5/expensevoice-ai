import uuid
from datetime import datetime

from pydantic import BaseModel


class AlertOut(BaseModel):
    id: uuid.UUID
    purchase_id: uuid.UUID
    alert_type: str
    message: str
    severity: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
