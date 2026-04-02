"""
PaddleOCR (open source) — extraction texte depuis image locale.

Dépendances : pip install paddleocr paddlepaddle
(langue fr par défaut ; use_angle_cls pour orientation)
"""
from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path

from app.schemas.invoice_pipeline import OCRLineSpan, OCRResult, OCRWordSpan
from app.services.image_preprocessing import exif_transpose

logger = logging.getLogger(__name__)

# Instance lazy (PaddleOCR est lourd au chargement)
_ocr_engine = None


def _get_paddle_ocr():
    global _ocr_engine
    if _ocr_engine is not None:
        return _ocr_engine
    try:
        from paddleocr import PaddleOCR
    except ImportError as e:
        logger.warning("PaddleOCR non importable: %s", e)
        raise
    lang = os.getenv("PADDLEOCR_LANG", "fr").strip() or "fr"
    kw: dict = {"use_angle_cls": True, "lang": lang, "show_log": False}
    if os.getenv("PADDLEOCR_USE_GPU", "").lower() in ("1", "true", "yes"):
        kw["use_gpu"] = True
    try:
        _ocr_engine = PaddleOCR(**kw)
    except TypeError:
        kw.pop("show_log", None)
        _ocr_engine = PaddleOCR(**kw)
    return _ocr_engine


def extract_text_from_image(image_path: str) -> OCRResult:
    """
    Extrait le texte d'une image et retourne OCRResult (raw_text, lignes, confiance moyenne).
    """
    t0 = time.perf_counter()
    path = Path(image_path)
    if not path.is_file():
        return OCRResult(
            raw_text="",
            metadata={"provider": "paddleocr", "error": "file_not_found"},
        )

    try:
        ocr = _get_paddle_ocr()
    except Exception as e:
        return OCRResult(
            raw_text="",
            metadata={"provider": "paddleocr", "error": f"import_or_init:{e!s}"[:200]},
        )

    lines_out: list[OCRLineSpan] = []
    words_out: list[OCRWordSpan] = []
    confidences: list[float] = []

    path_for_ocr = str(path)
    tmp_path: str | None = None
    try:
        from PIL import Image

        img = Image.open(str(path))
        img = exif_transpose(img)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        img.save(tmp_path, format="PNG")
        path_for_ocr = tmp_path
    except Exception as ex:
        logger.debug("PaddleOCR EXIF/temp preprocess skipped: %s", ex)

    try:
        result = ocr.ocr(path_for_ocr, cls=True)
    except Exception as e:
        logger.warning("PaddleOCR.ocr failed: %s", e)
        return OCRResult(
            raw_text="",
            metadata={"provider": "paddleocr", "error": str(e)[:200], "latency_ms": int((time.perf_counter() - t0) * 1000)},
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if not result:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return OCRResult(
            raw_text="",
            lines=[],
            metadata={"provider": "paddleocr", "latency_ms": elapsed_ms},
        )

    # API PaddleOCR : liste de pages; chaque page = liste de [box, (text, score)]
    # Tri lecture (haut → bas, gauche → droite) pour factures multi-colonnes TN/FR.
    row_buf: list[
        tuple[float, float, str, float, tuple[float, float, float, float] | None]
    ] = []
    for page in result:
        if not page:
            continue
        for entry in page:
            if entry is None or len(entry) < 2:
                continue
            box = entry[0]
            tpair = entry[1]
            if isinstance(tpair, (list, tuple)) and len(tpair) >= 2:
                txt, score = str(tpair[0]), tpair[1]
            else:
                continue
            try:
                conf_f = float(score)
            except (TypeError, ValueError):
                conf_f = 0.0
            txt = txt.strip()
            if not txt:
                continue
            bbox_flat: tuple[float, float, float, float] | None = None
            ymin = xmin = 0.0
            try:
                if box and len(box) >= 4:
                    xs = [float(p[0]) for p in box]
                    ys = [float(p[1]) for p in box]
                    bbox_flat = (min(xs), min(ys), max(xs), max(ys))
                    ymin, xmin = bbox_flat[1], bbox_flat[0]
            except (TypeError, ValueError, IndexError):
                pass
            row_buf.append((ymin, xmin, txt, conf_f, bbox_flat))

    row_buf.sort(key=lambda r: (r[0], r[1]))

    text_lines: list[str] = []
    for _, _, txt, conf_f, bbox_flat in row_buf:
        confidences.append(conf_f)
        text_lines.append(txt)
        w = OCRWordSpan(text=txt, confidence=conf_f, bbox=bbox_flat)
        words_out.append(w)
        lines_out.append(OCRLineSpan(text=txt, confidence=conf_f, words=[w]))

    raw_text = "\n".join(text_lines)
    avg_conf = sum(confidences) / len(confidences) if confidences else None
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    return OCRResult(
        raw_text=raw_text,
        lines=lines_out,
        words=words_out,
        confidence=avg_conf,
        metadata={
            "provider": "paddleocr",
            "latency_ms": elapsed_ms,
            "line_count": len(lines_out),
        },
    )
