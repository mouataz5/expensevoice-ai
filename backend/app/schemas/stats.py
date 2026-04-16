from typing import List, Optional

from pydantic import BaseModel


class CategoryStat(BaseModel):
    category: Optional[str] = None
    total_amount: float
    count: int


class UserStat(BaseModel):
    user_id: str
    email: Optional[str] = None  # mapped from User for display
    total_amount: float
    count: int


class DailyStat(BaseModel):
    date: str  # YYYY-MM-DD
    total_amount: float
    count: int


class DashboardStats(BaseModel):
    total_amount_today: float
    total_amount_month: float
    purchases_today: int
    purchases_month: int
    inflow_today: float = 0.0
    outflow_today: float = 0.0
    inflow_month: float = 0.0
    outflow_month: float = 0.0
    gross_margin_month: float = 0.0
    net_profit_month: float = 0.0
    fixed_expenses_month: float = 0.0
    variable_expenses_month: float = 0.0
    poussins_sales_month: float = 0.0
    nourriture_sales_month: float = 0.0
    by_category: List[CategoryStat]
    top_users: List[UserStat]
    daily_trend_last_14_days: List[DailyStat]
