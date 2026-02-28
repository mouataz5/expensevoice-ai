import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, model_validator


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

    @model_validator(mode="before")
    @classmethod
    def orm_metadata(cls, data: Any) -> Any:
        if hasattr(data, "metadata_"):
            return {
                "id": data.id,
                "actor_user_id": data.actor_user_id,
                "actor_role": data.actor_role,
                "action": data.action,
                "entity_type": data.entity_type,
                "entity_id": data.entity_id,
                "message": data.message,
                "metadata": data.metadata_,
                "created_at": data.created_at,
            }
        return data
