import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import PURCHASES_READ_ALL, require_permission
from app.db.deps import get_db
from app.models.farm import Farm
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.purchase import PurchaseCreate, PurchaseOut

router = APIRouter(prefix="/purchases", tags=["purchases"])
DEFAULT_VAT_RATE = float(os.getenv("PURCHASE_DEFAULT_VAT_RATE", "0.19") or "0.19")


def _purchase_source(p: Purchase) -> str:
    return "voice" if (p.audio_file_path or "").strip() else "manual"


def _purchase_totals(p: Purchase) -> tuple[float, float, float, bool]:
    ttc = float(p.total_amount or 0.0)
    if ttc < 0:
        ttc = 0.0
    vat_rate = max(0.0, DEFAULT_VAT_RATE)
    if vat_rate <= 0:
        return ttc, 0.0, ttc, True
    ht = round(ttc / (1.0 + vat_rate), 3)
    tva = round(ttc - ht, 3)
    return ht, tva, ttc, True


def _purchase_to_out(
    p: Purchase,
    employee_email: str | None = None,
    farm_name: str | None = None,
) -> dict:
    data = PurchaseOut.model_validate(p).model_dump()
    ht, tva, ttc, estimated = _purchase_totals(p)
    data["source"] = _purchase_source(p)
    data["total_ht"] = ht
    data["total_tva"] = tva
    data["total_ttc"] = ttc
    data["is_tax_estimated"] = estimated
    if employee_email is not None:
        data["employee_email"] = employee_email
    if farm_name is not None:
        data["farm_name"] = farm_name
    return data


@router.post("", response_model=PurchaseOut)
def create_purchase(
    payload: PurchaseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    purchase_date = payload.purchase_date or datetime.utcnow()
    total = float(payload.quantity) * float(payload.unit_price)
    if not payload.farm_id:
        raise HTTPException(status_code=422, detail="farm_id is required")
    farm = db.execute(
        select(Farm).where(Farm.id == payload.farm_id, Farm.is_active == True)  # noqa: E712
    ).scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=422, detail="Invalid farm_id")

    item = Purchase(
        user_id=user.id,
        farm_id=farm.id,
        product_name=payload.product_name,
        category=payload.category,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        total_amount=total,
        purchase_date=purchase_date,
        status="approved",
    )

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/me", response_model=list[PurchaseOut])
def list_my_purchases(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    q: str | None = Query(None),
    transaction_type: str | None = Query(None),
    status: str | None = Query(None),
    source: str | None = Query(None),
    farm_id: str | None = Query(None),
    qty_min: int | None = Query(None, ge=0),
    qty_max: int | None = Query(None, ge=0),
    unit_price_min: float | None = Query(None, ge=0),
    unit_price_max: float | None = Query(None, ge=0),
    ht_min: float | None = Query(None, ge=0),
    ht_max: float | None = Query(None, ge=0),
    tva_min: float | None = Query(None, ge=0),
    tva_max: float | None = Query(None, ge=0),
    ttc_min: float | None = Query(None, ge=0),
    ttc_max: float | None = Query(None, ge=0),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    query = select(Purchase).where(Purchase.user_id == user.id, Purchase.is_deleted == False)
    if status:
        query = query.where(Purchase.status == status)
    if farm_id:
        query = query.where(Purchase.farm_id == farm_id)
    if transaction_type in ("buy", "sell"):
        query = query.where(Purchase.transaction_type == transaction_type)
    if qty_min is not None:
        query = query.where(Purchase.quantity >= qty_min)
    if qty_max is not None:
        query = query.where(Purchase.quantity <= qty_max)
    if unit_price_min is not None:
        query = query.where(Purchase.unit_price >= unit_price_min)
    if unit_price_max is not None:
        query = query.where(Purchase.unit_price <= unit_price_max)
    if ttc_min is not None:
        query = query.where(Purchase.total_amount >= ttc_min)
    if ttc_max is not None:
        query = query.where(Purchase.total_amount <= ttc_max)
    if date_from is not None:
        query = query.where(Purchase.created_at >= date_from)
    if date_to is not None:
        query = query.where(Purchase.created_at <= date_to)
    if q and q.strip():
        qq = f"%{q.strip()}%"
        query = query.where(
            or_(
                Purchase.product_name.ilike(qq),
                Purchase.category.ilike(qq),
                Purchase.transcription.ilike(qq),
            )
        )

    rows = db.execute(query.order_by(Purchase.created_at.desc())).scalars().all()
    farm_ids = [p.farm_id for p in rows if p.farm_id]
    farms_map: dict[str, str] = {}
    if farm_ids:
        farm_rows = db.execute(select(Farm.id, Farm.name).where(Farm.id.in_(farm_ids))).all()
        farms_map = {str(fid): name for fid, name in farm_rows}
    out = [_purchase_to_out(p, farm_name=farms_map.get(str(p.farm_id)) if p.farm_id else None) for p in rows]
    if source in ("voice", "manual"):
        out = [p for p in out if p.get("source") == source]
    if ht_min is not None:
        out = [p for p in out if (p.get("total_ht") or 0) >= ht_min]
    if ht_max is not None:
        out = [p for p in out if (p.get("total_ht") or 0) <= ht_max]
    if tva_min is not None:
        out = [p for p in out if (p.get("total_tva") or 0) >= tva_min]
    if tva_max is not None:
        out = [p for p in out if (p.get("total_tva") or 0) <= tva_max]
    return out[offset : offset + limit]


@router.get("/all")
def list_all_purchases(
    db: Session = Depends(get_db),
    _user: User = require_permission(PURCHASES_READ_ALL),
    q: str | None = Query(None),
    transaction_type: str | None = Query(None),
    status: str | None = Query(None),
    source: str | None = Query(None),
    farm_id: str | None = Query(None),
    qty_min: int | None = Query(None, ge=0),
    qty_max: int | None = Query(None, ge=0),
    unit_price_min: float | None = Query(None, ge=0),
    unit_price_max: float | None = Query(None, ge=0),
    ht_min: float | None = Query(None, ge=0),
    ht_max: float | None = Query(None, ge=0),
    tva_min: float | None = Query(None, ge=0),
    tva_max: float | None = Query(None, ge=0),
    ttc_min: float | None = Query(None, ge=0),
    ttc_max: float | None = Query(None, ge=0),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    query = (
        select(Purchase, User.email, Farm.name)
        .join(User, User.id == Purchase.user_id)
        .outerjoin(Farm, Farm.id == Purchase.farm_id)
        .where(Purchase.is_deleted == False)
    )
    if status:
        query = query.where(Purchase.status == status)
    if farm_id:
        query = query.where(Purchase.farm_id == farm_id)
    if transaction_type in ("buy", "sell"):
        query = query.where(Purchase.transaction_type == transaction_type)
    if qty_min is not None:
        query = query.where(Purchase.quantity >= qty_min)
    if qty_max is not None:
        query = query.where(Purchase.quantity <= qty_max)
    if unit_price_min is not None:
        query = query.where(Purchase.unit_price >= unit_price_min)
    if unit_price_max is not None:
        query = query.where(Purchase.unit_price <= unit_price_max)
    if ttc_min is not None:
        query = query.where(Purchase.total_amount >= ttc_min)
    if ttc_max is not None:
        query = query.where(Purchase.total_amount <= ttc_max)
    if date_from is not None:
        query = query.where(Purchase.created_at >= date_from)
    if date_to is not None:
        query = query.where(Purchase.created_at <= date_to)
    if q and q.strip():
        qq = f"%{q.strip()}%"
        query = query.where(
            or_(
                Purchase.product_name.ilike(qq),
                Purchase.category.ilike(qq),
                Purchase.transcription.ilike(qq),
                User.email.ilike(qq),
            )
        )

    rows = db.execute(query.order_by(Purchase.created_at.desc())).all()
    out = [_purchase_to_out(purchase, email, farm_name) for purchase, email, farm_name in rows]
    if source in ("voice", "manual"):
        out = [p for p in out if p.get("source") == source]
    if ht_min is not None:
        out = [p for p in out if (p.get("total_ht") or 0) >= ht_min]
    if ht_max is not None:
        out = [p for p in out if (p.get("total_ht") or 0) <= ht_max]
    if tva_min is not None:
        out = [p for p in out if (p.get("total_tva") or 0) >= tva_min]
    if tva_max is not None:
        out = [p for p in out if (p.get("total_tva") or 0) <= tva_max]
    return out[offset : offset + limit]
