from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
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
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
):
    now = datetime.now(timezone.utc)

    # Default range: current month -> today
    if not from_date:
        from_date = date(now.year, now.month, 1)
    if not to_date:
        to_date = date(now.year, now.month, now.day)

    # Convert to UTC datetimes (inclusive range)
    start_dt = datetime(
        from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc
    )
    end_dt = datetime(
        to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc
    ) + timedelta(days=1)

    start_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    # Today metrics
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

    # Range totals
    total_range = db.execute(
        select(func.coalesce(func.sum(Purchase.total_amount), 0))
        .select_from(Purchase)
        .where(
            Purchase.created_at >= start_dt,
            Purchase.created_at < end_dt,
        )
    ).scalar_one()

    count_range = db.execute(
        select(func.count(Purchase.id))
        .select_from(Purchase)
        .where(
            Purchase.created_at >= start_dt,
            Purchase.created_at < end_dt,
        )
    ).scalar_one()

    # By category (range)
    by_category_rows = db.execute(
        select(
            Purchase.category,
            func.coalesce(func.sum(Purchase.total_amount), 0).label(
                "total_amount"
            ),
            func.count(Purchase.id).label("count"),
        )
        .select_from(Purchase)
        .where(
            Purchase.created_at >= start_dt,
            Purchase.created_at < end_dt,
        )
        .group_by(Purchase.category)
        .order_by(func.coalesce(func.sum(Purchase.total_amount), 0).desc())
    ).all()

    by_category = [
        CategoryStat(
            category=r[0], total_amount=float(r[1]), count=int(r[2])
        )
        for r in by_category_rows
    ]

    # Top users (range)
    top_user_rows = db.execute(
        select(
            Purchase.user_id,
            func.coalesce(func.sum(Purchase.total_amount), 0).label(
                "total_amount"
            ),
            func.count(Purchase.id).label("count"),
        )
        .select_from(Purchase)
        .where(
            Purchase.created_at >= start_dt,
            Purchase.created_at < end_dt,
        )
        .group_by(Purchase.user_id)
        .order_by(func.coalesce(func.sum(Purchase.total_amount), 0).desc())
        .limit(10)
    ).all()

    user_ids = [r[0] for r in top_user_rows]
    users_map = {}
    if user_ids:
        users_list = db.execute(
            select(User.id, User.email).where(User.id.in_(user_ids))
        ).all()
        users_map = {str(u[0]): u[1] for u in users_list}

    top_users = [
        UserStat(
            user_id=str(r[0]),
            email=users_map.get(str(r[0])),
            total_amount=float(r[1]),
            count=int(r[2]),
        )
        for r in top_user_rows
    ]

    # Daily trend for the selected range
    daily_rows = db.execute(
        select(
            cast(Purchase.created_at, Date).label("day"),
            func.coalesce(func.sum(Purchase.total_amount), 0).label(
                "total_amount"
            ),
            func.count(Purchase.id).label("count"),
        )
        .select_from(Purchase)
        .where(
            Purchase.created_at >= start_dt,
            Purchase.created_at < end_dt,
        )
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
        total_amount_month=float(total_range),
        purchases_today=int(count_today),
        purchases_month=int(count_range),
        by_category=by_category,
        top_users=top_users,
        daily_trend_last_14_days=daily_trend,
    )
