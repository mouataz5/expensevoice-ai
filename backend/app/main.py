from fastapi import FastAPI

from app.db.base import Base
from app.db.session import engine
from app.models.user import User  # noqa: F401

app = FastAPI(title="ExpenseVoice AI API", version="0.1.0")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}
