from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.alerts import router as alerts_router
from app.core.dependencies import get_current_user
from app.api.auth import router as auth_router
from app.api.confirm import router as confirm_router
from app.api.dashboard import router as dashboard_router
from app.api.policies import router as policies_router
from app.api.policies_public import router as policies_public_router
from app.api.policies_read import router as policies_read_router
from app.api.extract import router as extract_router
from app.api.purchases import router as purchases_router
from app.api.users import router as users_router
from app.api.voice import router as voice_router
from app.core.seed import seed_admin, seed_director, seed_employee, seed_policies
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.alert import Alert  # noqa: F401
from app.models.policy import Policy  # noqa: F401
from app.models.purchase import Purchase  # noqa: F401
from app.models.user import User  # noqa: F401

app = FastAPI(title="ExpenseVoice AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_admin(db)
        seed_director(db)
        seed_employee(db)
        seed_policies(db)
    finally:
        db.close()


app.include_router(auth_router)
app.include_router(purchases_router)
app.include_router(voice_router)
app.include_router(extract_router)
app.include_router(confirm_router)
app.include_router(dashboard_router)
app.include_router(alerts_router)
app.include_router(policies_router)
app.include_router(policies_public_router)
app.include_router(policies_read_router)
app.include_router(users_router)


@app.get("/api/me")
def me(user: User = Depends(get_current_user)):
    return {"id": str(user.id), "email": user.email, "role": user.role}


@app.get("/health")
def health():
    return {"status": "ok"}
