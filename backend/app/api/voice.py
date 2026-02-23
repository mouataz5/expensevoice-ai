import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.deps import get_db
from app.models.purchase import Purchase
from app.models.user import User
from app.services.stt import transcribe_audio

router = APIRouter(prefix="/api/purchases", tags=["voice"])

AUDIO_DIR = os.getenv("AUDIO_DIR", "storage/audio")

ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/mp4",
    "audio/webm",
}


@router.post("/record")
async def record_purchase_voice(
    audio: UploadFile = File(...),
    language: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if audio.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio type: {audio.content_type}",
        )

    os.makedirs(AUDIO_DIR, exist_ok=True)

    ext = os.path.splitext(audio.filename or "")[1] or ".audio"
    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(AUDIO_DIR, filename)

    with open(file_path, "wb") as f:
        content = await audio.read()
        f.write(content)

    try:
        text = transcribe_audio(file_path, language=language)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Transcription failed: {str(e)}"
        ) from e

    item = Purchase(
        user_id=user.id,
        product_name="(from_voice)",
        category=None,
        quantity=1,
        unit_price=0,
        total_amount=0,
        status="pending",
        audio_file_path=file_path,
        transcription=text,
        purchase_date=datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return {
        "purchase_id": str(item.id),
        "transcription": text,
        "status": item.status,
        "audio_file_path": item.audio_file_path,
    }
