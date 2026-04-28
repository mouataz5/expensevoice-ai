from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from io import BytesIO, StringIO
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.deps import get_db
from app.models.invoice import Invoice
from app.models.user import User

router = APIRouter(prefix="/invoices", tags=["invoice-business"])


def _extract_items(inv: Invoice) -> list[dict[str, Any]]:
    extracted = dict(inv.extracted_json or {})
    items = extracted.get("items") or []
    if isinstance(items, list):
        return [dict(x) for x in items if isinstance(x, dict)]
    return []


def _extract_totals(inv: Invoice) -> dict[str, Any]:
    extracted = dict(inv.extracted_json or {})
    totals = extracted.get("totals") or {}
    return dict(totals) if isinstance(totals, dict) else {}


def _date_bounds(from_date: date | None, to_date: date | None) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if not from_date:
        from_date = date(now.year, now.month, 1)
    if not to_date:
        to_date = date(now.year, now.month, now.day)
    start_dt = datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
    end_dt = datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc) + timedelta(days=1)
    return start_dt, end_dt


def _query_user_invoices(db: Session, user: User, start_dt: datetime, end_dt: datetime):
    q = (
        select(Invoice)
        .where(
            Invoice.user_id == user.id,
            Invoice.created_at >= start_dt,
            Invoice.created_at < end_dt,
        )
        .order_by(Invoice.created_at.desc())
    )
    return db.execute(q).scalars().all()


@router.get("/export/csv")
def export_invoices_csv(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
):
    start_dt, end_dt = _date_bounds(from_date, to_date)
    invoices = _query_user_invoices(db, user, start_dt, end_dt)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "invoice_id",
            "created_at",
            "status",
            "transaction_type",
            "supplier_name",
            "invoice_number",
            "invoice_date",
            "currency",
            "total_ht",
            "total_tva",
            "total_ttc",
            "item_description",
            "item_quantity",
            "item_unit_price",
            "item_total",
        ]
    )

    for inv in invoices:
        totals = _extract_totals(inv)
        items = _extract_items(inv)
        currency = ((inv.extracted_json or {}).get("currency") if isinstance(inv.extracted_json, dict) else None) or "TND"
        base = [
            str(inv.id),
            inv.created_at.isoformat() if inv.created_at else "",
            inv.status,
            inv.transaction_type,
            inv.supplier_name or "",
            inv.invoice_number or "",
            ((inv.extracted_json or {}).get("invoice_date") if isinstance(inv.extracted_json, dict) else "") or "",
            currency,
            totals.get("htva"),
            totals.get("tva"),
            totals.get("ttc"),
        ]
        if not items:
            writer.writerow(base + ["", "", "", ""])
            continue
        for it in items:
            writer.writerow(
                base
                + [
                    it.get("designation") or it.get("description") or "",
                    it.get("quantity"),
                    it.get("unit_price"),
                    it.get("line_total") or it.get("line_subtotal"),
                ]
            )

    output.seek(0)
    filename = f"invoices_{start_dt.date().isoformat()}_{(end_dt - timedelta(days=1)).date().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/excel")
def export_invoices_excel(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
):
    start_dt, end_dt = _date_bounds(from_date, to_date)
    invoices = _query_user_invoices(db, user, start_dt, end_dt)

    wb = Workbook()
    ws = wb.active
    ws.title = "Invoices"
    ws.append(
        [
            "invoice_id",
            "created_at",
            "status",
            "transaction_type",
            "supplier_name",
            "invoice_number",
            "invoice_date",
            "currency",
            "total_ht",
            "total_tva",
            "total_ttc",
            "item_description",
            "item_quantity",
            "item_unit_price",
            "item_total",
        ]
    )

    for inv in invoices:
        totals = _extract_totals(inv)
        items = _extract_items(inv)
        currency = ((inv.extracted_json or {}).get("currency") if isinstance(inv.extracted_json, dict) else None) or "TND"
        base = [
            str(inv.id),
            inv.created_at.isoformat() if inv.created_at else "",
            inv.status,
            inv.transaction_type,
            inv.supplier_name or "",
            inv.invoice_number or "",
            ((inv.extracted_json or {}).get("invoice_date") if isinstance(inv.extracted_json, dict) else "") or "",
            currency,
            totals.get("htva"),
            totals.get("tva"),
            totals.get("ttc"),
        ]
        if not items:
            ws.append(base + ["", "", "", ""])
            continue
        for it in items:
            ws.append(
                base
                + [
                    it.get("designation") or it.get("description") or "",
                    it.get("quantity"),
                    it.get("unit_price"),
                    it.get("line_total") or it.get("line_subtotal"),
                ]
            )

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"invoices_{start_dt.date().isoformat()}_{(end_dt - timedelta(days=1)).date().isoformat()}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/analytics/expenses-per-month")
def expenses_per_month(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
):
    start_dt, end_dt = _date_bounds(from_date, to_date)
    invoices = _query_user_invoices(db, user, start_dt, end_dt)
    agg: dict[str, float] = defaultdict(float)
    for inv in invoices:
        if inv.transaction_type != "buy":
            continue
        totals = _extract_totals(inv)
        ttc = totals.get("ttc")
        try:
            amount = float(ttc if ttc is not None else (inv.total_ttc or 0))
        except (TypeError, ValueError):
            amount = 0.0
        key = inv.created_at.strftime("%Y-%m") if inv.created_at else "unknown"
        agg[key] += amount
    return [{"month": k, "total_amount": round(v, 3)} for k, v in sorted(agg.items())]


@router.get("/analytics/expenses-per-supplier")
def expenses_per_supplier(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
):
    start_dt, end_dt = _date_bounds(from_date, to_date)
    invoices = _query_user_invoices(db, user, start_dt, end_dt)
    agg: dict[str, float] = defaultdict(float)
    for inv in invoices:
        if inv.transaction_type != "buy":
            continue
        supplier = (inv.supplier_name or "Unknown").strip() or "Unknown"
        totals = _extract_totals(inv)
        ttc = totals.get("ttc")
        try:
            amount = float(ttc if ttc is not None else (inv.total_ttc or 0))
        except (TypeError, ValueError):
            amount = 0.0
        agg[supplier] += amount
    rows = [{"supplier_name": k, "total_amount": round(v, 3)} for k, v in agg.items()]
    rows.sort(key=lambda x: x["total_amount"], reverse=True)
    return rows


@router.get("/analytics/top-products")
def top_products(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=20, ge=1, le=100),
):
    start_dt, end_dt = _date_bounds(from_date, to_date)
    invoices = _query_user_invoices(db, user, start_dt, end_dt)
    amount_by_product: dict[str, float] = defaultdict(float)
    count_by_product: dict[str, int] = defaultdict(int)
    for inv in invoices:
        for it in _extract_items(inv):
            name = (it.get("designation") or it.get("description") or "").strip()
            if not name:
                continue
            lt = it.get("line_total") or it.get("line_subtotal")
            try:
                amount = float(lt or 0)
            except (TypeError, ValueError):
                amount = 0.0
            amount_by_product[name] += amount
            count_by_product[name] += 1
    rows = [
        {
            "product_name": name,
            "total_amount": round(amount_by_product[name], 3),
            "count": count_by_product[name],
        }
        for name in amount_by_product
    ]
    rows.sort(key=lambda x: x["total_amount"], reverse=True)
    return rows[:limit]

