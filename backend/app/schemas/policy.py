import uuid
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

PolicyType = Literal["limits", "categories"]


class PolicyOut(BaseModel):
    id: uuid.UUID
    policy_type: str
    rule: Dict[str, Any]
    is_active: bool

    model_config = {"from_attributes": True}


class LimitsRule(BaseModel):
    max_per_purchase: float = Field(ge=0)
    daily_limit_default: float = Field(ge=0)


class CategoriesRule(BaseModel):
    allowed: List[str] = Field(default_factory=list)


class PolicyUpdate(BaseModel):
    rule: Dict[str, Any]
    is_active: Optional[bool] = None
