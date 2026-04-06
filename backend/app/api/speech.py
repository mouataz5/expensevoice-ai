"""
API Speech : transcription Whisper + facture vocale (Whisper → Groq).
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.core.config import MAX_AUDIO_BYTES
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.models.user import User
from app.services.speech.voice_to_invoice_service import (
    parse_voice_to_invoice,
    voice_purchase_to_extraction_response,
)
from app.services.speech.whisper_service import transcribe_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/speech", tags=["speech"])

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


def _validate_audio(audio: UploadFile, raw: bytes) -> None:
    ct_full = (audio.content_type or "").strip().lower()
    ct = ct_full.split(";", 1)[0]
    if ct not in ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Format audio non supporté: {audio.content_type}",
        )
    if len(raw) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Fichier audio trop volumineux (max 10 Mo)")
    if len(raw) < 64:
        raise HTTPException(status_code=400, detail="Fichier audio vide ou trop court")


def _ext_for_mime(ct: str) -> str:
    ct = ct.split(";", 1)[0].strip().lower()
    if ct in ("audio/mp4", "audio/x-m4a", "audio/m4a"):
        return "m4a"
    if ct == "audio/mpeg":
        return "mp3"
    if ct in ("audio/wav", "audio/x-wav"):
        return "wav"
    if "ogg" in ct:
        return "ogg"
    if ct == "audio/aac":
        return "aac"
    if ct == "audio/x-caf":
        return "caf"
    return "webm"


class TranscribeResponse(BaseModel):
    success: bool = True
    text: str
    language: str
    confidence: float | None = Field(None, description="Probabilité langue / qualité indicative")


class ParseInvoiceVoiceResponse(BaseModel):
    success: bool
    transcription: dict
    invoice: dict
    voice_purchase: dict = Field(
        default_factory=dict,
        description="JSON structuré Groq (lignes achat/vente, TND)",
    )


@router.post("/transcribe", response_model=TranscribeResponse)
@limiter.limit("20/minute")
async def transcribe_speech(
    request: Request,
    audio: Annotated[UploadFile, File(...)],
    language: Annotated[str | None, Form()] = None,
    user: User = Depends(get_current_user),
):
    """
    Transcription seule (Whisper). Langue : `auto` / vide = détection automatique.
    """
    if user.role not in ("employee", "director", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    raw = await audio.read()
    _validate_audio(audio, raw)

    ct = (audio.content_type or "").strip().lower().split(";", 1)[0]
    ext = _ext_for_mime(ct)
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        lang = (language or "").strip() or None
        if lang and lang.lower() == "auto":
            lang = None
        try:
            out = transcribe_file(tmp_path, language=lang)
        except TimeoutError:
            raise HTTPException(status_code=504, detail="Transcription trop longue (timeout serveur)")
        except ValueError as e:
            if str(e) == "audio_empty":
                raise HTTPException(status_code=400, detail="Audio vide")
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FileNotFoundError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            logger.exception("transcribe_speech failed")
            raise HTTPException(status_code=500, detail=f"Transcription échouée: {e!s}") from e

        return TranscribeResponse(
            success=True,
            text=out.get("text") or "",
            language=out.get("language") or "unknown",
            confidence=out.get("confidence"),
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@router.post("/parse-invoice", response_model=ParseInvoiceVoiceResponse)
@limiter.limit("10/minute")
async def parse_invoice_from_voice(
    request: Request,
    audio: Annotated[UploadFile | None, File()] = None,
    text: Annotated[str | None, Form()] = None,
    transaction_type: Annotated[str, Form()] = "buy",
    language: Annotated[str | None, Form()] = None,
    debug: Annotated[str, Form()] = "false",
    user: User = Depends(get_current_user),
):
    """
    Texte structuré (Groq) + enveloppe `invoice` pour l'app existante.

    Fournir **soit** `text` (multipart), **soit** `audio` (Whisper puis Groq).
    Si les deux sont présents, le texte saisi / collé prime (pas de re-transcription).
    """
    if user.role not in ("employee", "director", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    tt = (transaction_type or "buy").strip().lower()
    if tt not in ("sell", "buy"):
        tt = "buy"

    text_in = (text or "").strip()
    tmp_path: str | None = None
    stt_out: dict

    try:
        if text_in:
            stt_out = {
                "text": text_in,
                "language": None,
                "confidence": None,
                "duration_sec": None,
            }
        else:
            if audio is None:
                raise HTTPException(
                    status_code=400,
                    detail="Envoyez le champ multipart `text` ou un fichier `audio`.",
                )
            raw = await audio.read()
            _validate_audio(audio, raw)

            ct = (audio.content_type or "").strip().lower().split(";", 1)[0]
            ext = _ext_for_mime(ct)
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name

            lang = (language or "").strip() or None
            if lang and lang.lower() == "auto":
                lang = None

            try:
                stt_out = transcribe_file(tmp_path, language=lang)
            except TimeoutError:
                raise HTTPException(status_code=504, detail="Transcription trop longue (timeout serveur)")
            except ValueError as e:
                if str(e) == "audio_empty":
                    raise HTTPException(status_code=400, detail="Audio vide")
                raise HTTPException(status_code=400, detail=str(e)) from e
            except Exception as e:
                logger.exception("parse_invoice STT failed")
                raise HTTPException(status_code=500, detail=f"Transcription échouée: {e!s}") from e

        out_text = (stt_out.get("text") or "").strip()
        if not out_text:
            raise HTTPException(
                status_code=422,
                detail="Aucun texte — fournissez du texte ou un audio compréhensible.",
            )

        _ = debug  # réservé (logs / double pipeline)
        voice_purchase = await parse_voice_to_invoice(out_text, transaction_type=tt)
        inv_resp = voice_purchase_to_extraction_response(
            raw_text=out_text,
            voice_purchase=voice_purchase,
            transaction_type=tt,
        )

        return ParseInvoiceVoiceResponse(
            success=bool(inv_resp.success),
            transcription={
                "text": out_text,
                "language": stt_out.get("language"),
                "confidence": stt_out.get("confidence"),
                "duration_sec": stt_out.get("duration_sec"),
            },
            invoice=inv_resp.model_dump(mode="json"),
            voice_purchase=voice_purchase,
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
