import uuid
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

PolicyType = Literal["limits", "categories", "finance_taxonomy", "approval_workflow"]


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


class FinanceTaxonomyRule(BaseModel):
    products: List[str] = Field(default_factory=list)
    fixed_expense_categories: List[str] = Field(default_factory=list)
    variable_expense_categories: List[str] = Field(default_factory=list)
    sales_categories: List[str] = Field(default_factory=list)


class ApprovalWorkflowRule(BaseModel):
    require_admin_approval: bool = True
    allow_director_approval: bool = True
    monthly_closing_enabled: bool = True
    monthly_closing_day: int = Field(default=28, ge=1, le=31)
