from typing import List, Optional

from pydantic import BaseModel


class CategoryStat(BaseModel):
    category: Optional[str] = None
    total_amount: float
    count: int


class UserStat(BaseModel):
    user_id: str
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
    by_category: List[CategoryStat]
    top_users: List[UserStat]
    daily_trend_last_14_days: List[DailyStat]
