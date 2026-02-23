from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.purchases import router as purchases_router
from app.api.users import router as users_router
from app.api.voice import router as voice_router
from app.core.seed import seed_admin, seed_director
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.purchase import Purchase  # noqa: F401
from app.models.user import User  # noqa: F401

app = FastAPI(title="ExpenseVoice AI API")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_admin(db)
        seed_director(db)
    finally:
        db.close()


app.include_router(auth_router)
app.include_router(purchases_router)
app.include_router(voice_router)
app.include_router(dashboard_router)
app.include_router(users_router)


@app.get("/health")
def health():
    return {"status": "ok"}
