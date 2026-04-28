"""
PaddleOCR + PP-StructureV3 (PaddleX) : OCR pleine page, détection de mise en page et
reconnaissance de tableaux. Produit `structured_tables` au format grille consommé
par le pipeline facture (même modèle que les tables Surya).
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

from app.schemas.invoice_pipeline import OCRLineSpan, OCRResult, OCRWordSpan
from app.services.ocr.paddle_html_table_parser import surya_compatible_table_from_paddle_result
from app.services.image_preprocessing import exif_transpose

logger = logging.getLogger(__name__)

_pp_structure_engine: Any | None = None


def is_paddle_structure_supported() -> bool:
    """Indique si l'installation peut charger PP-StructureV3 (extra `paddlex[ocr]`)."""
    try:
        from paddleocr import PPStructureV3  # noqa: F401
        from paddlex.utils.deps import DependencyError  # noqa: F401
    except ImportError:
        return False
    return True


def _env_bool(key: str, default: str = "0") -> bool:
    return (os.getenv(key, default) or default).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _get_pp_structure_engine() -> Any:
    global _pp_structure_engine
    if _pp_structure_engine is not None:
        return _pp_structure_engine
    if not is_paddle_structure_supported():
        raise RuntimeError("PP-StructureV3 indisponible (installer paddlex[ocr])")
    from paddleocr import PPStructureV3

    if _env_bool("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "1"):
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

    lang = os.getenv("PADDLEOCR_LANG", "fr").strip() or "fr"
    kw: dict[str, Any] = {
        "lang": lang,
        "use_table_recognition": True,
        "use_formula_recognition": False,
        "use_chart_recognition": False,
        "use_seal_recognition": False,
        "use_region_detection": False,
    }
    _pp_structure_engine = PPStructureV3(**kw)
    return _pp_structure_engine


def _overall_ocr_to_spans(overall: Any) -> tuple[list[OCRLineSpan], list[OCRWordSpan], list[float]]:
    texts: list[str] = []
    boxes_rows: list[Any] = []
    scores: list[float] = []
    if overall is None:
        return [], [], []
    try:
        texts = list(overall.get("rec_texts") or [])
    except Exception:
        texts = []
    try:
        raw_boxes = overall.get("rec_boxes")
        if hasattr(raw_boxes, "tolist"):
            boxes_rows = raw_boxes.tolist()
        elif raw_boxes is not None:
            boxes_rows = list(raw_boxes)
    except Exception:
        boxes_rows = []
    try:
        sc = overall.get("rec_scores")
        if sc is not None:
            scores = [float(x) for x in list(sc)]
    except Exception:
        scores = []

    row_buf: list[tuple[float, float, str, float, tuple[float, float, float, float] | None]] = []
    for i, txt in enumerate(texts):
        t = str(txt).strip()
        if not t:
            continue
        conf = float(scores[i]) if i < len(scores) else 0.0
        bbox: tuple[float, float, float, float] | None = None
        ymin = xmin = 0.0
        if i < len(boxes_rows):
            b = boxes_rows[i]
            try:
                x1, y1, x2, y2 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
                bbox = (x1, y1, x2, y2)
                ymin, xmin = y1, x1
            except (TypeError, ValueError, IndexError):
                pass
        row_buf.append((ymin, xmin, t, conf, bbox))

    row_buf.sort(key=lambda r: (r[0], r[1]))
    lines_out: list[OCRLineSpan] = []
    words_out: list[OCRWordSpan] = []
    confidences: list[float] = []
    for _, _, txt, conf_f, bbox_flat in row_buf:
        confidences.append(conf_f)
        w = OCRWordSpan(text=txt, confidence=conf_f, bbox=bbox_flat)
        words_out.append(w)
        lines_out.append(OCRLineSpan(text=txt, confidence=conf_f, words=[w]))
    return lines_out, words_out, confidences


def _collect_tables_from_page(page: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        page_index = page.get("page_index")
    except Exception:
        page_index = None
    table_list = []
    try:
        table_list = page.get("table_res_list") or []
    except Exception:
        table_list = []
    for ti, tr in enumerate(table_list):
        pred_html = None
        cell_box_list: list[Any] | None = None
        try:
            if hasattr(tr, "get"):
                pred_html = tr.get("pred_html")
                cell_box_list = tr.get("cell_box_list")
            if (pred_html is None or cell_box_list is None) and hasattr(tr, "json"):
                res = tr.json.get("res", {}) if isinstance(tr.json, dict) else {}
                pred_html = pred_html or res.get("pred_html")
                cell_box_list = cell_box_list or res.get("cell_box_list")
        except Exception:
            pred_html, cell_box_list = None, None
        tbl = surya_compatible_table_from_paddle_result(
            page_index=page_index,
            table_index=ti,
            pred_html=str(pred_html) if pred_html else None,
            cell_box_list=list(cell_box_list) if cell_box_list is not None else None,
        )
        if tbl.get("n_cells", 0) > 0:
            out.append(tbl)
    return out


def extract_document_with_pp_structure(image_path: str) -> OCRResult:
    """
    Exécute PP-StructureV3 sur une image (facture / devis scanné).

    Retourne un `OCRResult` avec `metadata.provider=paddle_structure`,
    `structured_tables` (grilles normalisées), et le texte reconstruit depuis l’OCR global.
    """
    t0 = time.perf_counter()
    path = Path(image_path)
    if not path.is_file():
        return OCRResult(
            raw_text="",
            metadata={
                "provider": "paddle_structure",
                "error": "file_not_found",
            },
        )

    try:
        engine = _get_pp_structure_engine()
    except Exception as e:
        logger.warning("PP-Structure init failed: %s", e)
        return OCRResult(
            raw_text="",
            metadata={
                "provider": "paddle_structure",
                "error": f"init:{e!s}"[:220],
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            },
        )

    path_for_pred = str(path)
    tmp_path: str | None = None
    try:
        from PIL import Image

        img = Image.open(str(path))
        img = exif_transpose(img)
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        img.save(tmp_path, format="PNG")
        path_for_pred = tmp_path
    except Exception as ex:
        logger.debug("PP-Structure EXIF/temp preprocess skipped: %s", ex)

    try:
        use_ori = _env_bool("PADDLE_PP_USE_DOC_ORIENTATION", "1")
        use_unwarp = _env_bool("PADDLE_PP_USE_DOC_UNWARP", "0")
        pages = engine.predict(
            path_for_pred,
            use_doc_orientation_classify=use_ori,
            use_doc_unwarping=use_unwarp,
            use_table_recognition=True,
        )
    except Exception as e:
        logger.warning("PP-Structure predict failed: %s", e)
        return OCRResult(
            raw_text="",
            metadata={
                "provider": "paddle_structure",
                "error": str(e)[:220],
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            },
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if not pages:
        return OCRResult(
            raw_text="",
            metadata={
                "provider": "paddle_structure",
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            },
        )

    page = pages[0]
    overall = page.get("overall_ocr_res")
    lines_out, words_out, confidences = _overall_ocr_to_spans(overall)
    raw_text = "\n".join(w.text for w in words_out)

    all_tables: list[dict[str, Any]] = []
    for p in pages:
        all_tables.extend(_collect_tables_from_page(p))

    avg_conf = sum(confidences) / len(confidences) if confidences else None
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    layout_preview: list[dict[str, Any]] = []
    try:
        pr_list = page.get("parsing_res_list") or []
        for blk in pr_list[:60]:
            try:
                layout_preview.append(
                    {
                        "label": getattr(blk, "label", None),
                        "bbox": getattr(blk, "bbox", None),
                        "content_excerpt": (getattr(blk, "content", "") or "")[:200],
                    }
                )
            except Exception:
                continue
    except Exception:
        pass

    return OCRResult(
        raw_text=raw_text,
        lines=lines_out,
        words=words_out,
        confidence=avg_conf,
        metadata={
            "provider": "paddle_structure",
            "structure_engine": "PP-StructureV3",
            "structured_tables": all_tables[:20],
            "layout_blocks_preview": layout_preview,
            "latency_ms": elapsed_ms,
            "line_count": len(lines_out),
            "table_count": len(all_tables),
        },
    )


__all__ = [
    "extract_document_with_pp_structure",
    "is_paddle_structure_supported",
]
