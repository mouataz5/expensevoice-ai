"""
Microsoft Table Transformer (détection + structure) + OCR Paddle par cellule.

Produit `structured_tables` au même format grille que PP-Structure / Surya
(`surya_table_extractor`, `invoice_line_autocorrect` en aval).

Dépendances optionnelles : torch, transformers, timm (voir requirements / .env.example).
Sans ces libs, `is_tatr_available()` est False et le provider ne doit pas être seul dans la chaîne.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.schemas.invoice_pipeline import OCRLineSpan, OCRResult, OCRWordSpan
from app.services.image_preprocessing import exif_transpose

logger = logging.getLogger(__name__)

# Labels Hugging Face — microsoft/table-transformer-structure-recognition
_STRUCTURE_CELL_LABEL_IDS = frozenset({3, 4, 5})
# 3 table column header, 4 table projected row header, 5 table spanning cell

_det_processor = None
_det_model = None
_struct_processor = None
_struct_model = None
_device: str | None = None


def is_tatr_available() -> bool:
    try:
        import torch  # noqa: F401
        from transformers import AutoImageProcessor, TableTransformerForObjectDetection  # noqa: F401
    except ImportError:
        return False
    return True


def _resolve_device() -> str:
    global _device
    if _device is not None:
        return _device
    want = (os.getenv("TATR_DEVICE") or "").strip().lower()
    if want in ("cuda", "gpu") or (os.getenv("TATR_USE_GPU", "").lower() in ("1", "true", "yes")):
        try:
            import torch

            _device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            _device = "cpu"
    else:
        _device = "cpu"
    return _device


def _get_detection_models():
    global _det_processor, _det_model
    if _det_model is not None:
        return _det_processor, _det_model
    from transformers import AutoImageProcessor, TableTransformerForObjectDetection

    name = os.getenv("TATR_DETECTION_MODEL", "microsoft/table-transformer-detection").strip()
    _det_processor = AutoImageProcessor.from_pretrained(name)
    _det_model = TableTransformerForObjectDetection.from_pretrained(name)
    dev = _resolve_device()
    _det_model.to(dev)
    _det_model.eval()
    return _det_processor, _det_model


def _get_structure_models():
    global _struct_processor, _struct_model
    if _struct_model is not None:
        return _struct_processor, _struct_model
    from transformers import AutoImageProcessor, TableTransformerForObjectDetection

    name = os.getenv(
        "TATR_STRUCTURE_MODEL",
        "microsoft/table-transformer-structure-recognition",
    ).strip()
    _struct_processor = AutoImageProcessor.from_pretrained(name)
    _struct_model = TableTransformerForObjectDetection.from_pretrained(name)
    dev = _resolve_device()
    _struct_model.to(dev)
    _struct_model.eval()
    return _struct_processor, _struct_model


@dataclass
class _Box:
    x0: float
    y0: float
    x1: float
    y1: float
    label_id: int
    score: float

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2.0


def _detection_table_label_ids(model) -> set[int]:
    id2l: dict = getattr(model.config, "id2label", None) or {}
    out: set[int] = set()
    for k, v in id2l.items():
        try:
            kid = int(k)
        except (TypeError, ValueError):
            continue
        name = str(v).lower().strip()
        if name == "table" or ("table" in name and "rotated" not in name):
            out.add(kid)
    return out if out else {0}


def _run_detection(image, processor, model) -> list[_Box]:
    import torch

    dev = _resolve_device()
    table_ids = _detection_table_label_ids(model)
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(dev) for k, v in inputs.items()}
    th = float(os.getenv("TATR_DETECTION_THRESHOLD", "0.6"))
    with torch.no_grad():
        outputs = model(**inputs)
    tgt = torch.tensor([[image.size[1], image.size[0]]], device=dev, dtype=torch.long)
    res = processor.post_process_object_detection(outputs, threshold=th, target_sizes=tgt)[0]
    boxes: list[_Box] = []
    for sc, lab, box in zip(res["scores"], res["labels"], res["boxes"]):
        lid = int(lab.item())
        if lid not in table_ids:
            continue
        b = box.cpu().tolist()
        boxes.append(
            _Box(float(b[0]), float(b[1]), float(b[2]), float(b[3]), lid, float(sc.item()))
        )
    boxes.sort(key=lambda x: -x.score * (x.x1 - x.x0) * (x.y1 - x.y0))
    return boxes


def _run_structure(image, processor, model) -> list[_Box]:
    import torch

    dev = _resolve_device()
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(dev) for k, v in inputs.items()}
    th = float(os.getenv("TATR_STRUCTURE_THRESHOLD", "0.6"))
    with torch.no_grad():
        outputs = model(**inputs)
    tgt = torch.tensor([[image.size[1], image.size[0]]], device=dev, dtype=torch.long)
    res = processor.post_process_object_detection(outputs, threshold=th, target_sizes=tgt)[0]
    out: list[_Box] = []
    for sc, lab, box in zip(res["scores"], res["labels"], res["boxes"]):
        lid = int(lab.item())
        if lid not in _STRUCTURE_CELL_LABEL_IDS:
            continue
        b = box.cpu().tolist()
        out.append(
            _Box(float(b[0]), float(b[1]), float(b[2]), float(b[3]), lid, float(sc.item()))
        )
    return out


def _cluster_rows(boxes: list[_Box], *, y_tol: float) -> list[list[_Box]]:
    if not boxes:
        return []
    sy = sorted(boxes, key=lambda b: (b.yc, b.xc))
    rows: list[list[_Box]] = []
    for b in sy:
        placed = False
        for row in rows:
            mean_y = sum(x.yc for x in row) / len(row)
            if abs(b.yc - mean_y) <= y_tol:
                row.append(b)
                placed = True
                break
        if not placed:
            rows.append([b])
    rows.sort(key=lambda r: min(x.yc for x in r))
    for row in rows:
        row.sort(key=lambda b: b.xc)
    return rows


def _assign_grid_indices(row_groups: list[list[_Box]]) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for ri, row in enumerate(row_groups):
        for ci, b in enumerate(row):
            is_hdr = b.label_id in (3, 4)
            cells.append(
                {
                    "row_id": ri,
                    "col_id": ci,
                    "text": "",
                    "bbox": [b.x0, b.y0, b.x1, b.y1],
                    "is_header": is_hdr,
                }
            )
    return cells


def _ocr_cells_paddle(pil_image: Any, cells: list[dict[str, Any]]) -> None:
    try:
        from app.services.ocr.paddle_ocr_service import _get_paddle_ocr
    except Exception as e:
        logger.warning("TATR cell OCR: Paddle init failed: %s", e)
        return
    try:
        paddle = _get_paddle_ocr()
    except Exception as e:
        logger.warning("TATR cell OCR: %s", e)
        return
    w, h = pil_image.size
    pad = max(1, int(min(w, h) * 0.005))
    for c in cells:
        bb = c.get("bbox")
        if not bb or len(bb) < 4:
            continue
        try:
            x0 = max(0, int(float(bb[0])) - pad)
            y0 = max(0, int(float(bb[1])) - pad)
            x1 = min(w, int(float(bb[2])) + pad)
            y1 = min(h, int(float(bb[3])) + pad)
        except (TypeError, ValueError):
            continue
        if x1 <= x0 + 1 or y1 <= y0 + 1:
            continue
        crop = pil_image.crop((x0, y0, x1, y1))
        arr = np.array(crop.convert("RGB"))
        try:
            raw = paddle.ocr(arr, cls=True)
        except TypeError:
            raw = paddle.ocr(arr)
        parts: list[str] = []
        confs: list[float] = []
        if not raw:
            continue
        for page in raw:
            if not page:
                continue
            for entry in page:
                if entry is None or len(entry) < 2:
                    continue
                tpair = entry[1]
                if isinstance(tpair, (list, tuple)) and len(tpair) >= 2:
                    txt, score = str(tpair[0]), float(tpair[1])
                    if txt.strip():
                        parts.append(txt.strip())
                        confs.append(score)
        c["text"] = " ".join(parts).strip()
        if confs:
            c["_ocr_conf"] = sum(confs) / len(confs)


def _table_dict(table_index: int, cells: list[dict[str, Any]]) -> dict[str, Any]:
    clean = []
    for c in cells:
        d = {
            k: v
            for k, v in c.items()
            if k in ("row_id", "col_id", "text", "bbox", "is_header")
        }
        clean.append(d)
    return {
        "table_idx": table_index,
        "page": 0,
        "cells": clean,
        "n_cells": len(clean),
        "source": "tatr_paddle",
    }


def _raw_text_from_cells(cells: list[dict[str, Any]]) -> str:
    by_row: dict[int, list[tuple[int, str]]] = {}
    for c in cells:
        rid = int(c.get("row_id", 0))
        cid = int(c.get("col_id", 0))
        t = (c.get("text") or "").strip()
        by_row.setdefault(rid, []).append((cid, t))
    lines_out: list[str] = []
    for rid in sorted(by_row.keys()):
        cells_row = sorted(by_row[rid], key=lambda x: x[0])
        line = "  ".join(t for _, t in cells_row if t)
        if line.strip():
            lines_out.append(line)
    return "\n".join(lines_out)


def extract_document_with_tatr_paddle(image_path: str) -> OCRResult:
    """
    Détection + structure Table Transformer ; texte = OCR Paddle par cellule uniquement
    (pas d’agrégat OCR pleine page pour le corps du tableau).
    """
    t0 = time.perf_counter()
    path = Path(image_path)
    if not path.is_file():
        return OCRResult(
            raw_text="",
            metadata={"provider": "tatr_paddle", "error": "file_not_found"},
        )
    if not is_tatr_available():
        return OCRResult(
            raw_text="",
            metadata={
                "provider": "tatr_paddle",
                "error": "transformers_or_torch_missing",
            },
        )

    try:
        from PIL import Image

        img = Image.open(str(path))
        img = exif_transpose(img).convert("RGB")
    except Exception as e_img:
        logger.warning("TATR: image load failed: %s", e_img)
        return OCRResult(
            raw_text="",
            metadata={"provider": "tatr_paddle", "error": str(e_img)[:200]},
        )

    try:
        det_p, det_m = _get_detection_models()
        struct_p, struct_m = _get_structure_models()
    except Exception as e:
        logger.exception("TATR model load failed: %s", e)
        return OCRResult(
            raw_text="",
            metadata={
                "provider": "tatr_paddle",
                "error": f"model_load:{e!s}"[:220],
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            },
        )

    tables_out: list[dict[str, Any]] = []
    lines_out: list[OCRLineSpan] = []
    words_out: list[OCRWordSpan] = []
    confidences: list[float] = []
    cell_confs: list[float] = []

    use_full = os.getenv("TATR_SKIP_DETECTION", "").lower() in ("1", "true", "yes")
    regions: list[tuple[float, float, float, float]] = []
    if use_full:
        regions = [(0.0, 0.0, float(img.width), float(img.height))]
    else:
        try:
            det_boxes = _run_detection(img, det_p, det_m)
        except Exception as e:
            logger.warning("TATR detection failed, full image fallback: %s", e)
            det_boxes = []
        if det_boxes:
            for db in det_boxes[:3]:
                regions.append((db.x0, db.y0, db.x1, db.y1))
        else:
            regions = [(0.0, 0.0, float(img.width), float(img.height))]

    for ti, (rx0, ry0, rx1, ry1) in enumerate(regions):
        rx0, ry0 = max(0, rx0), max(0, ry0)
        rx1, ry1 = min(float(img.width), rx1), min(float(img.height), ry1)
        if rx1 <= rx0 + 8 or ry1 <= ry0 + 8:
            continue
        crop = img.crop((int(rx0), int(ry0), int(rx1), int(ry1)))
        try:
            struct_boxes = _run_structure(crop, struct_p, struct_m)
        except Exception as e:
            logger.warning("TATR structure failed table=%s: %s", ti, e)
            continue
        if len(struct_boxes) < 4:
            logger.info("TATR: too few cells (%s) for table %s", len(struct_boxes), ti)
            continue
        y_tol = max(8.0, 0.018 * crop.height)
        for b in struct_boxes:
            b.x0 += rx0
            b.x1 += rx0
            b.y0 += ry0
            b.y1 += ry0
        rows_g = _cluster_rows(struct_boxes, y_tol=y_tol)
        if len(rows_g) < 2:
            continue
        max_cols = max(len(r) for r in rows_g)
        if max_cols < 3:
            logger.info("TATR: grid too narrow (%s cols)", max_cols)
            continue
        cells = _assign_grid_indices(rows_g)
        if cells and not any(c.get("is_header") for c in cells):
            for c in cells:
                if int(c.get("row_id", -1)) == 0:
                    c["is_header"] = True
        _ocr_cells_paddle(img, cells)
        for c in cells:
            cf = c.get("_ocr_conf")
            if cf is not None:
                try:
                    cell_confs.append(float(cf))
                except (TypeError, ValueError):
                    pass
        tbl = _table_dict(ti, cells)
        if tbl["n_cells"] > 0:
            tables_out.append(tbl)

    chunks: list[str] = []
    for t in tables_out:
        chunk = _raw_text_from_cells(t.get("cells") or [])
        if chunk.strip():
            chunks.append(chunk)
    raw_text = "\n\n".join(chunks)

    line_conf = 0.78
    if cell_confs:
        line_conf = max(0.35, min(0.97, sum(cell_confs) / len(cell_confs)))
    for ln in raw_text.split("\n"):
        s = ln.strip()
        if not s:
            continue
        w = OCRWordSpan(text=s, confidence=line_conf, bbox=None)
        lines_out.append(OCRLineSpan(text=s, confidence=line_conf, words=[w]))
        words_out.append(w)
        confidences.append(line_conf)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    avg_c = sum(confidences) / len(confidences) if confidences else None

    meta: dict[str, Any] = {
        "provider": "tatr_paddle",
        "structure_engine": "microsoft/table-transformer",
        "structured_tables": tables_out[:20],
        "latency_ms": elapsed_ms,
        "table_count": len(tables_out),
        "line_count": len(lines_out),
    }
    if not tables_out:
        meta["reason"] = "no_reliable_table_grid"

    return OCRResult(
        raw_text=raw_text,
        lines=lines_out,
        words=words_out,
        confidence=avg_c,
        metadata=meta,
    )


__all__ = [
    "extract_document_with_tatr_paddle",
    "is_tatr_available",
]
