"""
Supplier auto-recognition from historical invoices (no extra table required).
"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice


def _norm_name(v: str | None) -> str:
    if not v:
        return ""
    return " ".join(v.strip().lower().split())


def suggest_supplier_from_history(
    db: Session,
    *,
    user_id: str,
    supplier_name: str | None,
    limit: int = 400,
) -> dict[str, Any] | None:
    """
    Returns best supplier fuzzy match from user's historical invoices.
    """
    query_name = _norm_name(supplier_name)
    if not query_name:
        return None

    rows = db.execute(
        select(Invoice.supplier_name)
        .where(Invoice.user_id == user_id, Invoice.supplier_name.is_not(None))
        .order_by(Invoice.created_at.desc())
        .limit(limit)
    ).all()
    candidates = []
    for (name,) in rows:
        n = _norm_name(name)
        if not n:
            continue
        candidates.append((name, n))
    if not candidates:
        return None

    best_name: str | None = None
    best_score = 0.0
    for original, normed in candidates:
        s = SequenceMatcher(None, query_name, normed).ratio()
        if s > best_score:
            best_score = s
            best_name = original

    if not best_name:
        return None
    if best_score < 0.74:
        return None

    return {
        "matched_supplier_name": best_name,
        "similarity": round(best_score, 4),
        "autofill_recommended": best_score >= 0.86,
    }


__all__ = ["suggest_supplier_from_history"]

