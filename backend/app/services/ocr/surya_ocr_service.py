"""
OCR principal optionnel via Surya : reconnaissance, analyse de mise en page, ordre de lecture, tables.

Dépendance optionnelle (`pip install surya-ocr` + PyTorch). Si le package est absent,
`is_surya_available()` est faux et le provider peut être ignoré par la chaîne OCR.

Variables utiles (voir aussi surya/settings.py et TORCH_DEVICE) :
- SURYA_ENABLE_LAYOUT : 1/0 (défaut 1) — LayoutPredictor + texte réordonné
- SURYA_ENABLE_TABLE : 1/0 (défaut 1 avec fournisseur Surya) — TableRecPredictor (lignes articles structurées)
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from PIL import Image

from app.schemas.invoice_pipeline import OCRLineSpan, OCRResult, OCRWordSpan

logger = logging.getLogger(__name__)


def is_surya_available() -> bool:
    try:
        import surya.detection  # noqa: F401
        import surya.recognition  # noqa: F401

        return True
    except Exception:
        return False


def _env_bool(key: str, default: str) -> bool:
    return (os.getenv(key, default) or default).strip().lower() in ("1", "true", "yes", "on")


@lru_cache(maxsize=1)
def _recognition_stack() -> tuple[Any, Any]:
    from surya.detection import DetectionPredictor
    from surya.foundation import FoundationPredictor
    from surya.recognition import RecognitionPredictor

    foundation = FoundationPredictor()
    return RecognitionPredictor(foundation), DetectionPredictor()


@lru_cache(maxsize=1)
def _layout_predictor() -> Any:
    from surya.foundation import FoundationPredictor
    from surya.layout import LayoutPredictor
    from surya.settings import settings

    return LayoutPredictor(FoundationPredictor(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT))


@lru_cache(maxsize=1)
def _table_predictor() -> Any:
    from surya.table_rec import TableRecPredictor

    return TableRecPredictor()


def _open_image(path: str) -> Image.Image:
    img = Image.open(path)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img


def _line_text(line: Any) -> str:
    if isinstance(line, dict):
        return str(line.get("text") or "").strip()
    return str(getattr(line, "text", "") or "").strip()


def _line_bbox(line: Any) -> tuple[float, float, float, float] | None:
    b = line.get("bbox") if isinstance(line, dict) else getattr(line, "bbox", None)
    if b is None:
        return None
    try:
        seq = list(b)[:4]
        if len(seq) < 4:
            return None
        return (float(seq[0]), float(seq[1]), float(seq[2]), float(seq[3]))
    except (TypeError, ValueError):
        return None


def _page_text_lines(page: Any) -> list[Any]:
    if page is None:
        return []
    if isinstance(page, dict):
        return list(page.get("text_lines") or [])
    tl = getattr(page, "text_lines", None)
    return list(tl) if tl is not None else []


def _first_page(prediction: Any) -> Any:
    if prediction is None:
        return None
    if isinstance(prediction, list):
        return prediction[0] if prediction else None
    return prediction


def _layout_boxes(layout_page: Any) -> list[dict[str, Any]]:
    if layout_page is None:
        return []
    raw = layout_page.get("bboxes") if isinstance(layout_page, dict) else getattr(layout_page, "bboxes", None)
    if not raw:
        return []
    out: list[dict[str, Any]] = []
    for b in raw:
        if isinstance(b, dict):
            bbox = b.get("bbox")
            pos = b.get("position")
            label = b.get("label")
        else:
            bbox = getattr(b, "bbox", None)
            pos = getattr(b, "position", None)
            label = getattr(b, "label", None)
        if not bbox or len(bbox) < 4:
            continue
        try:
            bb = tuple(float(x) for x in bbox[:4])
        except (TypeError, ValueError):
            continue
        pval: int | float = 999999
        if isinstance(pos, (int, float)):
            pval = pos
        elif pos is not None:
            try:
                pval = float(pos)
            except (TypeError, ValueError):
                pass
        out.append({"bbox": bb, "position": pval, "label": str(label or "")})
    out.sort(key=lambda x: float(x["position"]))
    return out


def _lines_with_indices(text_lines: list[Any]) -> list[tuple[int, tuple[float, float, float, float], str]]:
    acc: list[tuple[int, tuple[float, float, float, float], str]] = []
    for i, tl in enumerate(text_lines):
        t = _line_text(tl)
        bb = _line_bbox(tl)
        if t and bb:
            acc.append((i, bb, t))
    return acc


def _reading_order_text(
    text_lines: list[Any],
    layout_boxes: list[dict[str, Any]] | None,
) -> str:
    lines = _lines_with_indices(text_lines)
    if not lines:
        return ""
    if not layout_boxes:
        lines.sort(key=lambda x: (x[1][1], x[1][0]))
        return "\n".join(t for _, _, t in lines)

    used: set[int] = set()
    parts: list[str] = []
    for box in layout_boxes:
        bx = box["bbox"]
        inside: list[tuple[int, tuple[float, float, float, float], str]] = []
        for i, bb, t in lines:
            if i in used:
                continue
            cx = (bb[0] + bb[2]) / 2
            cy = (bb[1] + bb[3]) / 2
            if bx[0] <= cx <= bx[2] and bx[1] <= cy <= bx[3]:
                inside.append((i, bb, t))
        inside.sort(key=lambda x: (x[1][1], x[1][0]))
        for i, _, _ in inside:
            used.add(i)
        if inside:
            parts.append("\n".join(x[2] for x in inside))
    remaining = [(bb, t) for i, bb, t in lines if i not in used]
    remaining.sort(key=lambda x: (x[0][1], x[0][0]))
    if remaining:
        parts.append("\n".join(t for _, t in remaining))
    return "\n\n".join(p for p in parts if p)


def _simple_vertical_text(text_lines: list[Any]) -> str:
    lines = _lines_with_indices(text_lines)
    lines.sort(key=lambda x: (x[1][1], x[1][0]))
    return "\n".join(t for _, _, t in lines)


def _words_from_line(line: Any) -> list[OCRWordSpan]:
    raw = line.get("words") if isinstance(line, dict) else getattr(line, "words", None)
    if not raw:
        return []
    out: list[OCRWordSpan] = []
    for w in raw:
        if isinstance(w, dict):
            wt = str(w.get("text") or "")
            conf = w.get("confidence")
            bb = w.get("bbox")
        else:
            wt = str(getattr(w, "text", "") or "")
            conf = getattr(w, "confidence", None)
            bb = getattr(w, "bbox", None)
        bbox_tuple = None
        if bb is not None and len(bb) >= 4:
            try:
                bbox_tuple = tuple(float(x) for x in bb[:4])
            except (TypeError, ValueError):
                bbox_tuple = None
        try:
            c = float(conf) if conf is not None else None
        except (TypeError, ValueError):
            c = None
        if wt.strip():
            out.append(OCRWordSpan(text=wt, confidence=c, bbox=bbox_tuple))
    return out


def _build_ocr_line_spans(text_lines: list[Any]) -> list[OCRLineSpan]:
    spans: list[OCRLineSpan] = []
    indexed = _lines_with_indices(text_lines)
    indexed.sort(key=lambda x: (x[1][1], x[1][0]))
    for i, bb, _t in indexed:
        tl = text_lines[i]
        t = _line_text(tl)
        if not t or not bb:
            continue
        if isinstance(tl, dict):
            c_raw = tl.get("confidence")
        else:
            c_raw = getattr(tl, "confidence", None)
        try:
            lc = float(c_raw) if c_raw is not None else None
        except (TypeError, ValueError):
            lc = None
        words = _words_from_line(tl)
        spans.append(
            OCRLineSpan(
                text=t,
                confidence=lc,
                words=words,
            )
        )
    return spans


def _mean_conf(vals: list[float]) -> float | None:
    if not vals:
        return None
    return sum(vals) / len(vals)


def _flatten_prediction_pages(tp: Any) -> list[Any]:
    """Surya peut renvoyer une liste plate ou une liste de listes selon le modèle / version."""
    if not tp:
        return []
    if not isinstance(tp, list):
        return [tp]
    out: list[Any] = []
    for item in tp:
        if isinstance(item, list):
            out.extend(item)
        else:
            out.append(item)
    return out


def _table_page_to_json(page: Any) -> dict[str, Any] | None:
    if page is None:
        return None
    if isinstance(page, dict):
        d = page
    else:
        d = {
            "page": getattr(page, "page", None),
            "table_idx": getattr(page, "table_idx", None),
            "rows": getattr(page, "rows", None),
            "cols": getattr(page, "cols", None),
            "cells": getattr(page, "cells", None),
        }

    def _simplify_cell(c: Any) -> dict[str, Any]:
        if isinstance(c, dict):
            return {
                "text": c.get("text"),
                "bbox": list(c["bbox"][:4]) if c.get("bbox") is not None and len(c["bbox"]) >= 4 else None,
                "row_id": c.get("row_id"),
                "col_id": c.get("col_id"),
                "is_header": bool(c.get("is_header")),
            }
        return {
            "text": getattr(c, "text", None),
            "bbox": list(getattr(c, "bbox", [])[:4]) if getattr(c, "bbox", None) is not None else None,
            "row_id": getattr(c, "row_id", None),
            "col_id": getattr(c, "col_id", None),
            "is_header": bool(getattr(c, "is_header", False)),
        }

    cells = d.get("cells")
    if cells:
        cells_out = [_simplify_cell(c) for c in cells[:500]]
    else:
        cells_out = []
    return {
        "page": d.get("page"),
        "table_idx": d.get("table_idx"),
        "cells": cells_out,
        "n_cells": len(cells) if cells else 0,
    }


def extract_surya_document(image_path: str) -> OCRResult:
    """
    Exécute Surya sur la première page image et retourne un OCRResult aligné sur le reste du pipeline.
    """
    if not is_surya_available():
        raise RuntimeError("surya-ocr non installé (pip install surya-ocr + PyTorch)")

    img = _open_image(image_path)
    recognition_predictor, detection_predictor = _recognition_stack()
    predictions = recognition_predictor([img], det_predictor=detection_predictor)
    page = _first_page(predictions)
    text_lines = _page_text_lines(page)

    layout_meta: list[dict[str, Any]] = []
    boxes: list[dict[str, Any]] | None = None
    if _env_bool("SURYA_ENABLE_LAYOUT", "1"):
        try:
            layout_predictions = _layout_predictor()([img])
            lp = _first_page(layout_predictions)
            boxes = _layout_boxes(lp)
            layout_meta = [{"bbox": list(b["bbox"]), "position": b["position"], "label": b["label"]} for b in boxes]
        except Exception as e:
            logger.warning("Surya layout failed: %s", e)
            boxes = None

    raw_layout = _reading_order_text(text_lines, boxes)
    raw_simple = _simple_vertical_text(text_lines)
    raw_text = (raw_layout or raw_simple).strip()

    table_payload: list[dict[str, Any]] = []
    if _env_bool("SURYA_ENABLE_TABLE", "1"):
        try:
            tp = _table_predictor()([img])
            for tbl in _flatten_prediction_pages(tp):
                sj = _table_page_to_json(tbl)
                if sj:
                    table_payload.append(sj)
        except Exception as e:
            logger.warning("Surya table rec failed: %s", e)

    lines = _build_ocr_line_spans(text_lines)
    words: list[OCRWordSpan] = []
    for ln in lines:
        words.extend(ln.words)

    line_confs: list[float] = []
    for tl in text_lines:
        if isinstance(tl, dict):
            cr = tl.get("confidence")
        else:
            cr = getattr(tl, "confidence", None)
        try:
            if cr is not None:
                line_confs.append(float(cr))
        except (TypeError, ValueError):
            pass

    metadata: dict[str, Any] = {
        "provider": "surya",
        "layout_enabled": bool(boxes),
        "layout_boxes_preview": layout_meta[:80],
        "surya_tables": table_payload[:20],
        "text_fallback_vertical": raw_simple if raw_simple != raw_text else "",
    }

    return OCRResult(
        raw_text=raw_text,
        lines=lines,
        words=words,
        confidence=_mean_conf(line_confs),
        metadata=metadata,
    )


__all__ = [
    "extract_surya_document",
    "is_surya_available",
]