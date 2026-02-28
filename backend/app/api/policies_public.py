from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.deps import get_db
from app.models.policy import Policy
from app.models.user import User

router = APIRouter(prefix="/policies", tags=["policies-public"])


@router.get("/categories-public")
def categories_public(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    p = db.execute(
        select(Policy).where(
            Policy.policy_type == "categories",
            Policy.is_active.is_(True),
        )
    ).scalar_one_or_none()
    allowed = (p.rule or {}).get("allowed", []) if p else []
    return {"allowed": allowed}
