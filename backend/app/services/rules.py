from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.policy import Policy
from app.models.purchase import Purchase

# Part 2.4: Advanced anomaly detection thresholds
DAILY_SPIKE_RATIO = 2.0  # today vs 7-day average
UNIT_PRICE_DEVIATION_RATIO = 2.0  # vs category/user average
RECENT_CATEGORY_WINDOW = 10  # last N purchases to detect category shift
CATEGORY_CHANGE_MIN_RECENT = 3  # need at least this many recent to compare


def _get_policy(db: Session, policy_type: str) -> dict:
    p = db.execute(
        select(Policy).where(
            Policy.policy_type == policy_type,
            Policy.is_active.is_(True),
        )
    ).scalar_one_or_none()
    return p.rule if p else {}


def get_allowed_categories(db: Session) -> list[str]:
    """Return allowed categories from active policy, or empty list if none."""
    rule = _get_policy(db, "categories")
    return list(rule.get("allowed", []) or [])


def _start_of_today_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)


def evaluate_rules_and_create_alerts(
    db: Session, purchase: Purchase
) -> list[Alert]:
    alerts: list[Alert] = []

    limits = _get_policy(db, "limits")
    categories = _get_policy(db, "categories")

    max_per_purchase = float(limits.get("max_per_purchase", 0) or 0)
    daily_limit_default = float(limits.get("daily_limit_default", 0) or 0)
    allowed_categories = categories.get("allowed", [])

    if (
        allowed_categories
        and purchase.category
        and purchase.category not in allowed_categories
    ):
        alerts.append(
            Alert(
                purchase_id=purchase.id,
                alert_type="category_not_allowed",
                severity="critical",
                message=f"Category '{purchase.category}' is not allowed.",
            )
        )

    if max_per_purchase > 0 and float(purchase.total_amount) > max_per_purchase:
        alerts.append(
            Alert(
                purchase_id=purchase.id,
                alert_type="max_per_purchase",
                severity="warning",
                message=f"Purchase amount {float(purchase.total_amount)} exceeds max_per_purchase={max_per_purchase}.",
            )
        )

    if daily_limit_default > 0:
        start_today = _start_of_today_utc()
        sum_today = db.execute(
            select(
                func.coalesce(func.sum(Purchase.total_amount), 0)
            )
            .select_from(Purchase)
            .where(
                Purchase.user_id == purchase.user_id,
                Purchase.status == "approved",
                Purchase.created_at >= start_today,
                Purchase.is_deleted == False,
            )
        ).scalar_one()

        if float(sum_today) > daily_limit_default:
            alerts.append(
                Alert(
                    purchase_id=purchase.id,
                    alert_type="daily_limit",
                    severity="critical",
                    message=f"Daily total {float(sum_today)} exceeds daily_limit_default={daily_limit_default} for this user.",
                )
            )

    # Part 2.4: Daily spike vs last 7-day average
    start_today = _start_of_today_utc()
    end_today = start_today + timedelta(days=1)
    start_7d = start_today - timedelta(days=7)
    sum_today_val = db.execute(
        select(func.coalesce(func.sum(Purchase.total_amount), 0))
        .select_from(Purchase)
        .where(
            Purchase.user_id == purchase.user_id,
            Purchase.is_deleted == False,
            Purchase.created_at >= start_today,
            Purchase.created_at < end_today,
        )
    ).scalar_one() or 0
    sum_7d = db.execute(
        select(func.coalesce(func.sum(Purchase.total_amount), 0))
        .select_from(Purchase)
        .where(
            Purchase.user_id == purchase.user_id,
            Purchase.is_deleted == False,
            Purchase.created_at >= start_7d,
            Purchase.created_at < start_today,
        )
    ).scalar_one() or 0
    avg_7d = float(sum_7d) / 7.0 if sum_7d else 0
    if avg_7d > 0 and float(sum_today_val) > DAILY_SPIKE_RATIO * avg_7d:
        alerts.append(
            Alert(
                purchase_id=purchase.id,
                alert_type="daily_spike",
                severity="warning",
                message=f"Today's total ({sum_today_val:.2f}) is >{DAILY_SPIKE_RATIO}x the last 7-day average ({avg_7d:.2f}).",
            )
        )

    # Part 2.4: Abnormal unit price vs category average
    if purchase.category:
        avg_price_row = db.execute(
            select(func.avg(Purchase.unit_price))
            .select_from(Purchase)
            .where(
                Purchase.category == purchase.category,
                Purchase.id != purchase.id,
                Purchase.is_deleted == False,
            )
        ).first()
        if avg_price_row and avg_price_row[0] is not None:
            avg_cat = float(avg_price_row[0])
            if avg_cat > 0 and float(purchase.unit_price) > UNIT_PRICE_DEVIATION_RATIO * avg_cat:
                alerts.append(
                    Alert(
                        purchase_id=purchase.id,
                        alert_type="abnormal_unit_price",
                        severity="warning",
                        message=f"Unit price {float(purchase.unit_price):.2f} is >{UNIT_PRICE_DEVIATION_RATIO}x the category '{purchase.category}' average ({avg_cat:.2f}).",
                    )
                )

    # Part 2.4: Sudden category change (user usually buys X, now Y)
    recent = (
        db.execute(
            select(Purchase.category)
            .select_from(Purchase)
            .where(
                Purchase.user_id == purchase.user_id,
                Purchase.is_deleted == False,
                Purchase.id != purchase.id,
            )
            .order_by(Purchase.created_at.desc())
            .limit(RECENT_CATEGORY_WINDOW)
        )
        .scalars()
        .all()
    )
    recent_cats = [r for r in recent if r]
    if len(recent_cats) >= CATEGORY_CHANGE_MIN_RECENT and purchase.category:
        from collections import Counter
        counts = Counter(recent_cats)
        most_common_cat, _ = counts.most_common(1)[0]
        if most_common_cat != purchase.category and counts[most_common_cat] >= len(recent_cats) // 2:
            alerts.append(
                Alert(
                    purchase_id=purchase.id,
                    alert_type="category_change",
                    severity="info",
                    message=f"Unusual category: recent purchases were mostly '{most_common_cat}', now '{purchase.category}'.",
                )
            )

    for a in alerts:
        db.add(a)
    if alerts:
        db.commit()

    return alerts
