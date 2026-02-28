import asyncio
import io
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import Date, cast, desc, func, select
from sqlalchemy.orm import Session

from app.core.permissions import EXPORT_READ, require_permission
from app.db.deps import get_db
from app.models.purchase import Purchase
from app.models.user import User

router = APIRouter(prefix="/export", tags=["export"])


def _range_filters(from_date: date | None, to_date: date | None):
    filters = [Purchase.is_deleted == False]
    if from_date:
        start_dt = datetime(
            from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc
        )
        filters.append(Purchase.created_at >= start_dt)
    if to_date:
        end_dt = datetime(
            to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc
        ) + timedelta(days=1)
        filters.append(Purchase.created_at < end_dt)
    return filters


def _draw_bar(c: canvas.Canvas, x: float, y: float, w: float, h: float, pct: float) -> None:
    c.rect(x, y, w, h, stroke=1, fill=0)
    fill_w = max(0.0, min(1.0, float(pct))) * w
    if fill_w > 0:
        c.rect(x, y, fill_w, h, stroke=0, fill=1)


def _build_stats_pdf_sync(
    total_count: int,
    total_amount: float,
    trend: list[tuple[str, float]],
    top_categories: list[tuple[str, float]],
    top_users: list[tuple[str, float, int]],
    from_date: date | None,
    to_date: date | None,
) -> bytes:
    """Part 2.5: CPU-bound PDF build runs in thread."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    title = "تقرير الإحصائيات - نظام عبّاس"
    period = f"الفترة: {from_date or '—'} → {to_date or '—'}"
    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, title)
    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(40, y, period[:80])
    y -= 24
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "ملخص")
    y -= 14
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"عدد العمليات: {total_count}")
    y -= 12
    c.drawString(40, y, f"مجموع المبالغ: {total_amount:.2f}")
    y -= 20
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "أكثر التصنيفات (Top 5)")
    y -= 14
    c.setFont("Helvetica", 9)
    max_cat = max((v for _, v in top_categories), default=1.0)
    bar_x, bar_w, bar_h = 240, 240, 10
    for name, val in top_categories:
        if y < 110:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica", 9)
        c.drawString(40, y, str(name)[:30])
        c.drawRightString(220, y, f"{val:.2f}")
        _draw_bar(c, bar_x, y - 2, bar_w, bar_h, (val / max_cat) if max_cat else 0)
        y -= 14
    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "أفضل المستخدمين (Top 5)")
    y -= 14
    c.setFont("Helvetica", 9)
    for uid, val, cnt in top_users:
        if y < 110:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica", 9)
        uid_short = (uid[:8] + "…") if len(uid) > 8 else uid
        c.drawString(40, y, f"User: {uid_short}")
        c.drawString(160, y, f"Count: {cnt}")
        c.drawRightString(520, y, f"{val:.2f}")
        y -= 12
    y -= 12
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "تطور المبالغ حسب اليوم")
    y -= 14
    c.setFont("Helvetica", 9)
    chart_x, chart_y = 40, y - 140
    chart_w, chart_h = 520, 120
    c.rect(chart_x, chart_y, chart_w, chart_h, stroke=1, fill=0)
    if trend:
        max_v = max((v for _, v in trend), default=1.0) or 1.0
        n = len(trend)
        step = chart_w / max(1, n - 1) if n > 1 else chart_w
        pts = []
        for i, (_, v) in enumerate(trend):
            px = chart_x + (i * step if n > 1 else 0)
            py = chart_y + (v / max_v) * chart_h
            pts.append((px, py))
        for i in range(1, len(pts)):
            c.line(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1])
        last = trend[-6:] if len(trend) > 6 else trend
        yy = chart_y - 12
        c.setFont("Helvetica", 8)
        c.drawString(40, yy, "آخر الأيام:")
        xlab = 100
        for d, v in last:
            c.drawString(xlab, yy, f"{d}:{v:.0f}")
            xlab += 70
    c.showPage()
    c.save()
    return buf.getvalue()


@router.get("/stats.pdf")
async def export_stats_pdf(
    db: Session = Depends(get_db),
    _user: User = require_permission(EXPORT_READ),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
):
    filters = _range_filters(from_date, to_date)

    # Summary
    q_sum = (
        select(
            func.count(Purchase.id).label("cnt"),
            func.coalesce(func.sum(Purchase.total_amount), 0).label("total"),
        )
        .select_from(Purchase)
    )
    if filters:
        q_sum = q_sum.where(*filters)
    row = db.execute(q_sum).first()
    total_count = int(row[0]) if row else 0
    total_amount = float(row[1]) if row and row[1] is not None else 0.0

    # Trend by day
    day_col = cast(Purchase.created_at, Date).label("day")
    q_trend = (
        select(
            day_col,
            func.coalesce(func.sum(Purchase.total_amount), 0).label("s"),
        )
        .select_from(Purchase)
        .group_by(cast(Purchase.created_at, Date))
        .order_by(cast(Purchase.created_at, Date).asc())
    )
    if filters:
        q_trend = q_trend.where(*filters)
    trend_rows = db.execute(q_trend).all()
    trend = [(str(r[0]), float(r[1])) for r in trend_rows]

    # Top categories
    cat_sum = func.coalesce(func.sum(Purchase.total_amount), 0).label("s")
    q_cat = (
        select(Purchase.category, cat_sum)
        .select_from(Purchase)
        .group_by(Purchase.category)
        .order_by(desc(cat_sum))
        .limit(5)
    )
    if filters:
        q_cat = q_cat.where(*filters)
    cat_rows = db.execute(q_cat).all()
    top_categories = [((r[0] or "—"), float(r[1])) for r in cat_rows]

    # Top users
    user_sum = func.coalesce(func.sum(Purchase.total_amount), 0).label("s")
    user_cnt = func.count(Purchase.id).label("c")
    q_user = (
        select(Purchase.user_id, user_sum, user_cnt)
        .select_from(Purchase)
        .group_by(Purchase.user_id)
        .order_by(desc(user_sum))
        .limit(5)
    )
    if filters:
        q_user = q_user.where(*filters)
    user_rows = db.execute(q_user).all()
    top_users = [(str(r[0]), float(r[1]), int(r[2])) for r in user_rows]

    # Part 2.5: Run PDF build in thread pool to avoid blocking event loop
    pdf_bytes = await asyncio.to_thread(
        _build_stats_pdf_sync,
        total_count,
        total_amount,
        trend,
        top_categories,
        top_users,
        from_date,
        to_date,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="stats.pdf"'},
    )
