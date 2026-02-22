from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.deps import get_db
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.stats import (
    CategoryStat,
    DashboardStats,
    DailyStat,
    UserStat,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    db: Session = Depends(get_db),
    _user: User = require_roles("director", "admin"),
):
    now = datetime.now(timezone.utc)
    start_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    start_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    # Totals + counts (today)
    total_today = db.execute(
        select(func.coalesce(func.sum(Purchase.total_amount), 0))
        .select_from(Purchase)
        .where(Purchase.created_at >= start_today)
    ).scalar_one()

    count_today = db.execute(
        select(func.count(Purchase.id))
        .select_from(Purchase)
        .where(Purchase.created_at >= start_today)
    ).scalar_one()

    # Totals + counts (month)
    total_month = db.execute(
        select(func.coalesce(func.sum(Purchase.total_amount), 0))
        .select_from(Purchase)
        .where(Purchase.created_at >= start_month)
    ).scalar_one()

    count_month = db.execute(
        select(func.count(Purchase.id))
        .select_from(Purchase)
        .where(Purchase.created_at >= start_month)
    ).scalar_one()

    # By category (month)
    by_category_rows = db.execute(
        select(
            Purchase.category,
            func.coalesce(func.sum(Purchase.total_amount), 0).label(
                "total_amount"
            ),
            func.count(Purchase.id).label("count"),
        )
        .where(Purchase.created_at >= start_month)
        .group_by(Purchase.category)
        .order_by(func.coalesce(func.sum(Purchase.total_amount), 0).desc())
    ).all()

    by_category = [
        CategoryStat(
            category=r[0], total_amount=float(r[1]), count=int(r[2])
        )
        for r in by_category_rows
    ]

    # Top users (month)
    top_user_rows = db.execute(
        select(
            Purchase.user_id,
            func.coalesce(func.sum(Purchase.total_amount), 0).label(
                "total_amount"
            ),
            func.count(Purchase.id).label("count"),
        )
        .where(Purchase.created_at >= start_month)
        .group_by(Purchase.user_id)
        .order_by(func.coalesce(func.sum(Purchase.total_amount), 0).desc())
        .limit(10)
    ).all()

    top_users = [
        UserStat(
            user_id=str(r[0]), total_amount=float(r[1]), count=int(r[2])
        )
        for r in top_user_rows
    ]

    # Daily trend last 14 days
    start_14 = start_today - timedelta(days=13)

    daily_rows = db.execute(
        select(
            cast(Purchase.created_at, Date).label("day"),
            func.coalesce(func.sum(Purchase.total_amount), 0).label(
                "total_amount"
            ),
            func.count(Purchase.id).label("count"),
        )
        .select_from(Purchase)
        .where(Purchase.created_at >= start_14)
        .group_by(cast(Purchase.created_at, Date))
        .order_by(cast(Purchase.created_at, Date).asc())
    ).all()

    daily_trend = [
        DailyStat(
            date=str(r[0]), total_amount=float(r[1]), count=int(r[2])
        )
        for r in daily_rows
    ]

    return DashboardStats(
        total_amount_today=float(total_today),
        total_amount_month=float(total_month),
        purchases_today=int(count_today),
        purchases_month=int(count_month),
        by_category=by_category,
        top_users=top_users,
        daily_trend_last_14_days=daily_trend,
    )
