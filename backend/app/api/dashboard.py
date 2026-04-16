import csv
import io
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import Date, cast, func, select, true
from sqlalchemy.orm import Session

from app.core.permissions import STATS_READ, require_permission
from app.db.deps import get_db
from app.models.purchase import Purchase
from app.models.policy import Policy
from app.models.user import User
from app.schemas.stats import (
    CategoryStat,
    DashboardStats,
    DailyStat,
    UserStat,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _get_taxonomy(db: Session) -> dict:
    p = db.execute(
        select(Policy).where(Policy.policy_type == "finance_taxonomy", Policy.is_active == True)  # noqa: E712
    ).scalar_one_or_none()
    return p.rule if p and isinstance(p.rule, dict) else {}


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    db: Session = Depends(get_db),
    _user: User = require_permission(STATS_READ),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    farm_id: str | None = Query(default=None),
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

    # Today metrics (aggregates always return one row)
    total_today_row = db.execute(
        select(func.coalesce(func.sum(Purchase.total_amount), 0))
        .select_from(Purchase)
        .where(
            Purchase.created_at >= start_today,
            Purchase.is_deleted == False,
            Purchase.farm_id == farm_id if farm_id else true(),
        )
    ).first()
    total_today = float(total_today_row[0]) if total_today_row else 0.0

    count_today_row = db.execute(
        select(func.count(Purchase.id))
        .select_from(Purchase)
        .where(
            Purchase.created_at >= start_today,
            Purchase.is_deleted == False,
            Purchase.farm_id == farm_id if farm_id else true(),
        )
    ).first()
    count_today = int(count_today_row[0]) if count_today_row else 0

    # Range totals
    total_range_row = db.execute(
        select(func.coalesce(func.sum(Purchase.total_amount), 0))
        .select_from(Purchase)
        .where(
            Purchase.created_at >= start_dt,
            Purchase.created_at < end_dt,
            Purchase.is_deleted == False,
            Purchase.farm_id == farm_id if farm_id else true(),
        )
    ).first()
    total_range = float(total_range_row[0]) if total_range_row else 0.0

    count_range_row = db.execute(
        select(func.count(Purchase.id))
        .select_from(Purchase)
        .where(
            Purchase.created_at >= start_dt,
            Purchase.created_at < end_dt,
            Purchase.is_deleted == False,
            Purchase.farm_id == farm_id if farm_id else true(),
        )
    ).first()
    count_range = int(count_range_row[0]) if count_range_row else 0

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
            Purchase.is_deleted == False,
            Purchase.farm_id == farm_id if farm_id else true(),
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
            Purchase.is_deleted == False,
            Purchase.farm_id == farm_id if farm_id else true(),
        )
        .group_by(Purchase.user_id)
        .order_by(func.coalesce(func.sum(Purchase.total_amount), 0).desc())
        .limit(10)
    ).all()

    user_ids = [r[0] for r in top_user_rows]
    users_map = {}
    if user_ids:
        users_list = db.execute(
            select(User.id, User.email).where(
                User.id.in_(user_ids), User.is_deleted == False
            )
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
            Purchase.is_deleted == False,
            Purchase.farm_id == farm_id if farm_id else true(),
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

    tx_filters = [
        Purchase.created_at >= start_dt,
        Purchase.created_at < end_dt,
        Purchase.is_deleted == False,
        Purchase.farm_id == farm_id if farm_id else true(),
    ]
    inflow_month = float(
        db.execute(
            select(func.coalesce(func.sum(Purchase.total_amount), 0)).where(
                *tx_filters,
                Purchase.transaction_type == "sell",
                Purchase.status == "approved",
            )
        ).scalar_one()
        or 0
    )
    outflow_month = float(
        db.execute(
            select(func.coalesce(func.sum(Purchase.total_amount), 0)).where(
                *tx_filters,
                Purchase.transaction_type == "buy",
                Purchase.status == "approved",
            )
        ).scalar_one()
        or 0
    )
    inflow_today = float(
        db.execute(
            select(func.coalesce(func.sum(Purchase.total_amount), 0)).where(
                Purchase.created_at >= start_today,
                Purchase.created_at < (start_today + timedelta(days=1)),
                Purchase.transaction_type == "sell",
                Purchase.status == "approved",
                Purchase.is_deleted == False,
                Purchase.farm_id == farm_id if farm_id else true(),
            )
        ).scalar_one()
        or 0
    )
    outflow_today = float(
        db.execute(
            select(func.coalesce(func.sum(Purchase.total_amount), 0)).where(
                Purchase.created_at >= start_today,
                Purchase.created_at < (start_today + timedelta(days=1)),
                Purchase.transaction_type == "buy",
                Purchase.status == "approved",
                Purchase.is_deleted == False,
                Purchase.farm_id == farm_id if farm_id else true(),
            )
        ).scalar_one()
        or 0
    )

    taxonomy = _get_taxonomy(db)
    fixed_cats = list(taxonomy.get("fixed_expense_categories", []) or [])
    variable_cats = list(taxonomy.get("variable_expense_categories", []) or [])

    fixed_expenses_month = 0.0
    variable_expenses_month = 0.0
    if fixed_cats:
        fixed_expenses_month = float(
            db.execute(
                select(func.coalesce(func.sum(Purchase.total_amount), 0)).where(
                    *tx_filters,
                    Purchase.category.in_(fixed_cats),
                    Purchase.status == "approved",
                )
            ).scalar_one()
            or 0
        )
    if variable_cats:
        variable_expenses_month = float(
            db.execute(
                select(func.coalesce(func.sum(Purchase.total_amount), 0)).where(
                    *tx_filters,
                    Purchase.category.in_(variable_cats),
                    Purchase.status == "approved",
                )
            ).scalar_one()
            or 0
        )

    poussins_sales_month = float(
        db.execute(
            select(func.coalesce(func.sum(Purchase.total_amount), 0)).where(
                *tx_filters,
                Purchase.transaction_type == "sell",
                Purchase.status == "approved",
                Purchase.product_name.ilike("%poussin%"),
            )
        ).scalar_one()
        or 0
    )
    nourriture_sales_month = float(
        db.execute(
            select(func.coalesce(func.sum(Purchase.total_amount), 0)).where(
                *tx_filters,
                Purchase.transaction_type == "sell",
                Purchase.status == "approved",
                Purchase.product_name.ilike("%nourrit%"),
            )
        ).scalar_one()
        or 0
    )
    gross_margin_month = inflow_month - outflow_month
    net_profit_month = inflow_month - (fixed_expenses_month + variable_expenses_month)

    return DashboardStats(
        total_amount_today=total_today,
        total_amount_month=total_range,
        purchases_today=count_today,
        purchases_month=count_range,
        inflow_today=inflow_today,
        outflow_today=outflow_today,
        inflow_month=inflow_month,
        outflow_month=outflow_month,
        gross_margin_month=gross_margin_month,
        net_profit_month=net_profit_month,
        fixed_expenses_month=fixed_expenses_month,
        variable_expenses_month=variable_expenses_month,
        poussins_sales_month=poussins_sales_month,
        nourriture_sales_month=nourriture_sales_month,
        by_category=by_category,
        top_users=top_users,
        daily_trend_last_14_days=daily_trend,
    )


@router.get("/finance-report")
def finance_report(
    db: Session = Depends(get_db),
    _user: User = require_permission(STATS_READ),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    farm_id: str | None = Query(default=None),
):
    stats = get_stats(db=db, _user=_user, from_date=from_date, to_date=to_date, farm_id=farm_id)
    return {
        "period": {"from": str(from_date) if from_date else None, "to": str(to_date) if to_date else None},
        "farm_id": farm_id,
        "kpis": stats.model_dump(),
    }


@router.get("/finance-report.csv")
def finance_report_csv(
    db: Session = Depends(get_db),
    _user: User = require_permission(STATS_READ),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    farm_id: str | None = Query(default=None),
):
    stats = get_stats(db=db, _user=_user, from_date=from_date, to_date=to_date, farm_id=farm_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["metric", "value"])
    for key, value in stats.model_dump().items():
        if isinstance(value, (list, dict)):
            continue
        writer.writerow([key, value])
    csv_content = buf.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="finance-report.csv"'},
    )
