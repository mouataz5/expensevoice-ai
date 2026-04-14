"""
Prétraitement image amont OCR / détection de tables (deskew, contraste, débruitage léger).

Réutilise les utilitaires historiques `app.services.image_preprocessing` et ajoute
une passe « document scan » optionnelle (redimensionnement borné, conservation du ratio).
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)

# Taille max du bord long pour stabilité OCR table (px.) — peut être surchargée.
_MAX_LONG_SIDE = int(os.getenv("TABLE_OCR_MAX_LONG_SIDE", "2400"))


def _env_preprocess_enabled() -> bool:
    return (os.getenv("SURYA_TABLE_PREPROCESS", "1") or "1").strip().lower() in ("1", "true", "yes", "on")


def deskew_image_pil(img: "Image.Image") -> "Image.Image":
    """
    Redressement léger : si OpenCV est disponible, estimation angle projection ; sinon retour inchangé.
    """
    try:
        import cv2  # type: ignore[import-untyped]
        import numpy as np
    except ImportError:
        return img

    try:
        gray = img.convert("L")
        arr = np.array(gray)
        arr = cv2.bitwise_not(arr)
        coords = np.column_stack(np.where(arr > 0))
        if coords.size < 50:
            return img
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle = angle - 90
        if abs(angle) < 0.4:
            return img
        angle_max = float(os.getenv("TABLE_DESKEW_MAX_DEG", "8") or "8")
        angle = max(-angle_max, min(angle_max, angle))
        h, w = arr.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        rotated = cv2.warpAffine(np.array(img.convert("RGB")), m, (w, h), borderValue=(255, 255, 255))
        from PIL import Image as PILImage

        return PILImage.fromarray(rotated)
    except Exception as e:
        logger.debug("deskew skipped: %s", e)
        return img


def normalize_brightness_contrast(img: "Image.Image") -> "Image.Image":
    """Contraste modéré + netteté légère (PIL only)."""
    from PIL import ImageEnhance, ImageFilter

    g = img.convert("L") if img.mode != "L" else img
    g = ImageEnhance.Contrast(g).enhance(1.25)
    return g.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=3))


def resize_preserving_aspect(img: "Image.Image", max_long: int | None = None) -> "Image.Image":
    max_long = max_long or _MAX_LONG_SIDE
    w, h = img.size
    m = max(w, h)
    if m <= max_long:
        return img
    scale = max_long / float(m)
    nw, nh = int(w * scale), int(h * scale)
    return img.resize((nw, nh), getattr(img, "LANCZOS", 1))


def preprocess_for_table_ocr(image_path: str, *, write_temp: bool = True) -> str:
    """
    Retourne le chemin d'une image prête pour Surya / table rec.

    Si désactivé (SURYA_TABLE_PREPROCESS=0) ou erreur, retourne `image_path` d'origine.
    Si write_temp, écrit un JPEG temporaire ; sinon retourne l'original (pas de fichier).
    """
    if not _env_preprocess_enabled() or not write_temp:
        return image_path
    p = Path(image_path)
    if not p.is_file():
        return image_path
    try:
        from PIL import Image

        img = Image.open(str(p))
        img = deskew_image_pil(img)
        img = normalize_brightness_contrast(img)
        img = resize_preserving_aspect(img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        fd, tmp = tempfile.mkstemp(suffix=".jpg", prefix="ev_table_")
        os.close(fd)
        img.save(tmp, format="JPEG", quality=92, optimize=True)
        return tmp
    except Exception as e:
        logger.warning("preprocess_for_table_ocr fallback original: %s", e)
        return image_path


__all__ = [
    "deskew_image_pil",
    "normalize_brightness_contrast",
    "preprocess_for_table_ocr",
    "resize_preserving_aspect",
]
