import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditOut(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID
    actor_role: str
    action: str
    entity_type: str
    entity_id: str
    message: str
    metadata: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
