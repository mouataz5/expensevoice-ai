"""
Prétraitement d'image pour OCR (photos téléphone).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)


def exif_transpose(img: "Image.Image") -> "Image.Image":
    try:
        from PIL import ImageOps

        return ImageOps.exif_transpose(img)
    except Exception:
        return img


def preprocess_variants(img: "Image.Image") -> list["Image.Image"]:
    """Variantes contrastées / sharp / resize pour Tesseract (même logique qu'avant)."""
    from PIL import ImageEnhance, ImageFilter

    variants = [img]

    gray = img.convert("L")
    variants.append(gray)

    contrast = ImageEnhance.Contrast(gray).enhance(2.0)
    sharp = contrast.filter(ImageFilter.SHARPEN)
    variants.append(sharp)

    w, h = img.size
    if max(w, h) < 3000:
        scale = 2 if max(w, h) < 2000 else 1.5
        big = img.resize((int(w * scale), int(h * scale)), getattr(img, "LANCZOS", 1))
        gray_big = big.convert("L")
        contrast_big = ImageEnhance.Contrast(gray_big).enhance(2.5)
        sharp_big = contrast_big.filter(ImageFilter.SHARPEN).filter(ImageFilter.SHARPEN)
        variants.append(sharp_big)

        for thresh in (130, 150, 170):
            bw = sharp_big.point(lambda x, t=thresh: 0 if x < t else 255, "1")
            variants.append(bw)

    try:
        import numpy as np
        from PIL import Image as _Img

        source_gray = sharp_big if max(w, h) < 3000 else gray
        arr = np.array(source_gray)
        c_val = 10
        blurred = _Img.fromarray(arr).filter(ImageFilter.GaussianBlur(radius=15))
        mean = np.array(blurred, dtype=np.float64)
        adaptive = ((arr.astype(np.float64) > (mean - c_val)) * 255).astype(np.uint8)
        variants.append(_Img.fromarray(adaptive))
    except (ImportError, NameError):
        pass

    return variants
