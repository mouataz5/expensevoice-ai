from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.policy import Policy
from app.models.purchase import Purchase


def _get_policy(db: Session, policy_type: str) -> dict:
    p = db.execute(
        select(Policy).where(
            Policy.policy_type == policy_type,
            Policy.is_active.is_(True),
        )
    ).scalar_one_or_none()
    return p.rule if p else {}


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

    for a in alerts:
        db.add(a)
    if alerts:
        db.commit()

    return alerts
