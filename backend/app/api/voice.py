import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.config import MAX_AUDIO_BYTES
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.db.deps import get_db
from app.models.purchase import Purchase
from app.models.user import User
from app.services.task_dispatcher import enqueue_voice_purchase_processing

router = APIRouter(prefix="/purchases", tags=["voice"])
logger = logging.getLogger(__name__)

# Private storage: NOT served by FastAPI static. Path stored in DB only.
STORAGE_DIR = Path(os.getenv("AUDIO_STORAGE_DIR", "storage/audio"))

ALLOWED_MIME = {
    "audio/webm",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/ogg",
    "audio/x-m4a",
    "audio/m4a",
    "audio/x-wav",
    "audio/aac",
    "audio/x-caf",
}


def validate_audio_file(audio: UploadFile, raw: bytes) -> None:
    ct_full = (audio.content_type or "").strip().lower()
    # Browsers often send values like "audio/webm;codecs=opus" — we only care about the base type.
    ct = ct_full.split(";", 1)[0]
    if ct not in ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported audio type: {audio.content_type}",
        )
    if len(raw) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large (max 10MB)")


@router.post("/record")
@limiter.limit("10/minute")
async def record_purchase_voice(
    request: Request,
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    language: str | None = Form(default=None),
    transaction_type: str | None = Form(default=None),  # "sell" | "buy"
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Part 1: Return immediately with processing_status=processing.
    Background: STT then extraction; set ready_for_review when done.
    """
    start = time.perf_counter()
    raw = await audio.read()
    validate_audio_file(audio, raw)

    # Normalize transaction_type
    tt = (transaction_type or "buy").strip().lower()
    if tt not in ("sell", "buy"):
        tt = "buy"

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    ct = (audio.content_type or "").strip().lower().split(";", 1)[0]
    ext = "webm"
    if ct in ("audio/mp4", "audio/x-m4a", "audio/m4a"):
        ext = "m4a"
    elif ct == "audio/mpeg":
        ext = "mp3"
    elif ct in ("audio/wav", "audio/x-wav"):
        ext = "wav"
    elif "ogg" in ct:
        ext = "ogg"
    elif ct == "audio/aac":
        ext = "aac"
    elif ct == "audio/x-caf":
        ext = "caf"

    filename = f"{uuid.uuid4()}.{ext}"
    path = STORAGE_DIR / filename
    path.write_bytes(raw)
    file_path = str(path)

    item = Purchase(
        user_id=user.id,
        product_name="(from_voice)",
        category=None,
        quantity=1,
        unit_price=0,
        total_amount=0,
        status="pending",
        transaction_type=tt,
        processing_status="processing",
        audio_file_path=file_path,
        transcription="",
        purchase_date=datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    enqueue_voice_purchase_processing(
        item.id,
        file_path,
        language or "ar",
        tt,
        background_tasks,
    )

    elapsed = time.perf_counter() - start
    logger.info(
        "record_purchase_voice response: purchase_id=%s transaction_type=%s response_ms=%.0f",
        item.id, tt, elapsed * 1000,
    )

    return {
        "purchase_id": str(item.id),
        "status": item.status,
        "processing_status": "processing",
        "transaction_type": tt,
        "audio_file_path": item.audio_file_path,
    }
