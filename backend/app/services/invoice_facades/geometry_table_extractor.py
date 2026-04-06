"""
Reconstruction de tableau depuis la géométrie des mots OCR (bbox), sans ordre texte plat.

Utilise les lignes / mots de `OCRResult` (Surya recognition) + zone Table du layout si dispo.
Complète `surya_table_extractor` (cellules Surya) quand celles-ci sont pauvres ou mal alignées.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from statistics import median
from typing import Any, Literal

from app.schemas.invoice_pipeline import InvoiceLineDraft, OCRResult
from app.utils.money import normalize_tunisian_invoice_amount, to_float_safe

from app.services.invoice_facades.surya_table_extractor import (
    TableRowModel,
    _HEADER_PATTERNS,
    _SKIP_ROW_DESC,
    _table_row_to_line_draft,
    validate_and_correct_rows,
)

logger = logging.getLogger(__name__)

ColumnRole = Literal[
    "designation",
    "unit",
    "quantity",
    "unit_price",
    "line_ht",
    "line_ttc",
    "unknown",
]

_NUM_FALLBACK: tuple[ColumnRole, ...] = ("quantity", "unit_price", "line_ht", "line_ttc")


@dataclass
class _WordBox:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def h(self) -> float:
        return max(0.1, self.y1 - self.y0)


def _words_from_ocr(ocr: OCRResult) -> list[_WordBox]:
    out: list[_WordBox] = []
    for ln in ocr.lines or []:
        for w in ln.words or []:
            t = (w.text or "").strip()
            if not t or not w.bbox or len(w.bbox) < 4:
                continue
            try:
                x0, y0, x1, y1 = float(w.bbox[0]), float(w.bbox[1]), float(w.bbox[2]), float(w.bbox[3])
            except (TypeError, ValueError):
                continue
            out.append(_WordBox(t, x0, y0, x1, y1))
    if not out and ocr.words:
        for w in ocr.words:
            t = (w.text or "").strip()
            if not t or not w.bbox or len(w.bbox) < 4:
                continue
            try:
                x0, y0, x1, y1 = float(w.bbox[0]), float(w.bbox[1]), float(w.bbox[2]), float(w.bbox[3])
            except (TypeError, ValueError):
                continue
            out.append(_WordBox(t, x0, y0, x1, y1))
    return out


def _filter_table_region(words: list[_WordBox], metadata: dict[str, Any]) -> list[_WordBox]:
    boxes = metadata.get("layout_boxes_preview") or []
    for b in boxes:
        if not isinstance(b, dict):
            continue
        lbl = str(b.get("label") or "").lower()
        if "table" not in lbl:
            continue
        bb = b.get("bbox")
        if not bb or len(bb) < 4:
            continue
        try:
            bx0, by0, bx1, by1 = float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])
        except (TypeError, ValueError):
            continue
        inside = [w for w in words if bx0 <= w.xc <= bx1 and by0 <= w.yc <= by1]
        if len(inside) >= 6:
            return inside
    return words


def _y_tolerance(words: list[_WordBox]) -> float:
    hs = [w.h for w in words]
    if not hs:
        return 10.0
    return max(10.0, float(median(hs)) * 0.5)


def _cluster_rows(words: list[_WordBox], tol: float) -> list[list[_WordBox]]:
    sy = sorted(words, key=lambda w: (w.yc, w.xc))
    rows: list[list[_WordBox]] = []
    for w in sy:
        if not rows:
            rows.append([w])
            continue
        mean_y = sum(x.yc for x in rows[-1]) / len(rows[-1])
        if abs(w.yc - mean_y) <= tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    return rows


def _page_width(words: list[_WordBox]) -> float:
    if not words:
        return 1000.0
    return max(w.x1 for w in words) - min(w.x0 for w in words) + 1.0


def _split_row_cells_by_x_gaps(row: list[_WordBox], page_w: float) -> list[list[_WordBox]]:
    """Découpe une ligne en cellules par grands écarts horizontaux ; seuil adaptatif si peu de colonnes."""
    if not row:
        return []
    rw = sorted(row, key=lambda w: w.x0)
    if len(rw) == 1:
        return [rw]
    gaps = [rw[i + 1].x0 - rw[i].x1 for i in range(len(rw) - 1)]
    med = float(median(gaps)) if gaps else 0.0
    mg = max(gap for gap in gaps) if gaps else med

    def _cut(mult: float, min_px: float) -> list[list[_WordBox]]:
        thresh = max(med * mult, page_w * 0.012, min_px, mg * 0.22)
        cells: list[list[_WordBox]] = []
        cur: list[_WordBox] = [rw[0]]
        for i in range(len(rw) - 1):
            if rw[i + 1].x0 - rw[i].x1 > thresh:
                cells.append(cur)
                cur = [rw[i + 1]]
            else:
                cur.append(rw[i + 1])
        cells.append(cur)
        return cells

    for mult, min_px in ((2.2, 10.0), (1.35, 6.0), (1.05, 4.0)):
        cells = _cut(mult, min_px)
        if len(cells) >= 4:
            return cells
    cells = _cut(1.05, 4.0)
    if len(cells) >= 4:
        return cells
    # En-têtes à tokens courts (UN / QTE / P.U) collés : une cellule par mot
    if len(rw) >= 4:
        avg_token_w = sum(w.x1 - w.x0 for w in rw) / len(rw)
        if avg_token_w < page_w * 0.12:
            return [[w] for w in rw]
    return cells


def _cell_text(cell: list[_WordBox]) -> str:
    return " ".join(w.text for w in sorted(cell, key=lambda w: w.x0))


def _is_header_row(row_words: list[_WordBox]) -> bool:
    blob = _cell_text(row_words).lower()
    hits = sum(1 for _role, pat in _HEADER_PATTERNS if pat.search(blob))
    return hits >= 2


def _map_header_cell_roles(header_cells: list[list[_WordBox]]) -> list[ColumnRole]:
    roles: list[ColumnRole] = []
    for cell in header_cells:
        t = _cell_text(cell)[:240]
        role: ColumnRole = "unknown"
        for rname, pat in _HEADER_PATTERNS:
            if pat.search(t):
                role = rname  # type: ignore[assignment]
                break
        roles.append(role)
    roles = list(roles)
    if not any(r == "designation" for r in roles):
        roles[0] = "designation"
    unk_i = [i for i, r in enumerate(roles) if r == "unknown"]
    fi = 0
    for i in unk_i:
        if fi < len(_NUM_FALLBACK):
            roles[i] = _NUM_FALLBACK[fi]
            fi += 1
    return roles


def _assign_row_to_columns(data_row: list[_WordBox], header_cells: list[list[_WordBox]]) -> list[list[_WordBox]]:
    centers: list[float] = []
    for hc in header_cells:
        xs = [w.xc for w in hc]
        centers.append(sum(xs) / len(xs))
    cols: list[list[_WordBox]] = [[] for _ in centers]
    for w in sorted(data_row, key=lambda w: w.xc):
        j = min(range(len(centers)), key=lambda k: abs(w.xc - centers[k]))
        cols[j].append(w)
    return cols


def _row_model_from_cells(
    cells: list[list[_WordBox]],
    roles: list[ColumnRole],
    row_id: int,
) -> TableRowModel | None:
    if len(cells) != len(roles):
        return None
    desc_parts: list[str] = []
    unit: str | None = None
    qty = pu = ht = ttc = None
    for cell, role in zip(cells, roles):
        txt = _cell_text(cell).strip()
        if not txt:
            continue
        if role == "designation":
            desc_parts.append(txt)
        elif role == "unit":
            unit = txt[:24]
        elif role == "quantity":
            qty = normalize_tunisian_invoice_amount(txt) or to_float_safe(txt)
        elif role == "unit_price":
            pu = normalize_tunisian_invoice_amount(txt) or to_float_safe(txt)
        elif role == "line_ht":
            ht = normalize_tunisian_invoice_amount(txt) or to_float_safe(txt)
        elif role == "line_ttc":
            ttc = normalize_tunisian_invoice_amount(txt) or to_float_safe(txt)
        elif role == "unknown":
            raw_num = re.sub(r"[^\d\s.,]", "", txt).strip()
            v = normalize_tunisian_invoice_amount(txt) if raw_num else None
            if v is None and raw_num:
                v = to_float_safe(raw_num)
            if v is not None and raw_num and len(raw_num) <= 22:
                if qty is None and v <= 10000 and abs(v - round(v)) < 0.05:
                    qty = float(round(v))
                elif pu is None:
                    pu = v
                elif ht is None:
                    ht = v
                elif ttc is None:
                    ttc = v
                else:
                    desc_parts.append(txt)
            else:
                desc_parts.append(txt)

    d = " ".join(desc_parts).strip()
    if not d and not any(x is not None for x in (qty, pu, ht, ttc)):
        return None
    return TableRowModel(
        description=d or None,
        unit=unit,
        quantity=qty,
        unit_price=pu,
        line_ht=ht,
        line_ttc=ttc,
        source_row_id=row_id,
    )


def extract_invoice_lines_from_word_geometry(
    ocr: OCRResult,
    metadata: dict[str, Any] | None = None,
) -> tuple[list[InvoiceLineDraft], dict[str, Any]]:
    """
    Extrait des lignes articles depuis les bbox des mots (groupement Y puis colonnes X).
    """
    meta = metadata if metadata is not None else dict(ocr.metadata or {})
    dbg: dict[str, Any] = {
        "applied_to_draft": False,
        "reason": "init",
        "source": "word_geometry",
    }
    words = _words_from_ocr(ocr)
    dbg["n_words_input"] = len(words)
    if len(words) < 6:
        dbg["reason"] = "too_few_words"
        return [], dbg

    words = _filter_table_region(words, meta)
    dbg["n_words_after_layout"] = len(words)
    if len(words) < 6:
        dbg["reason"] = "too_few_words_in_region"
        return [], dbg

    tol = _y_tolerance(words)
    dbg["y_tolerance"] = tol
    row_groups = _cluster_rows(words, tol)
    page_w = _page_width(words)

    hdr_idx: int | None = None
    for i, rw in enumerate(row_groups):
        if len(rw) >= 3 and _is_header_row(rw):
            hdr_idx = i
            break
    if hdr_idx is None:
        dbg["reason"] = "no_header_row"
        return [], dbg

    header_cells = _split_row_cells_by_x_gaps(row_groups[hdr_idx], page_w)
    if len(header_cells) < 4:
        dbg["reason"] = "too_few_columns"
        return [], dbg

    roles = _map_header_cell_roles(header_cells)
    dbg["column_roles"] = roles
    dbg["n_columns"] = len(header_cells)

    models: list[TableRowModel] = []
    for j, dr in enumerate(row_groups[hdr_idx + 1 :]):
        if len(dr) < 2:
            continue
        cells = _assign_row_to_columns(dr, header_cells)
        tm = _row_model_from_cells(cells, roles, j)
        if tm is None:
            continue
        dtext = (tm.description or "").strip()
        if dtext and _SKIP_ROW_DESC.search(dtext):
            continue
        if not dtext and not any(x is not None for x in (tm.line_ht, tm.quantity, tm.unit_price)):
            continue
        models.append(tm)

    if len(models) < 1:
        dbg["reason"] = "no_data_rows"
        return [], dbg

    models, corrections = validate_and_correct_rows(models)
    dbg["corrections"] = corrections

    drafts: list[InvoiceLineDraft] = []
    for r in models:
        d = _table_row_to_line_draft(r)
        if d.line_subtotal is not None or (d.quantity is not None and d.unit_price is not None):
            drafts.append(d)

    if len(drafts) < 1:
        dbg["reason"] = "no_valid_drafts"
        return [], dbg

    dbg["applied_to_draft"] = True
    dbg["reason"] = "ok"
    dbg["line_count"] = len(drafts)
    logger.info("geometry_table_extractor: %d line items from word layout", len(drafts))
    return drafts, dbg


def score_line_drafts(lines: list[InvoiceLineDraft] | None) -> float:
    """Score lignes structurées (préfère qté×PU≈HT et qtés non triviales)."""
    if not lines:
        return -1.0
    sc = 0.0
    for ln in lines:
        q = to_float_safe(ln.quantity) or 0.0
        pu = to_float_safe(ln.unit_price) or 0.0
        st = to_float_safe(ln.line_subtotal) or 0.0
        if st > 0:
            sc += 2.0
        if q > 0 and pu > 0 and st > 0:
            m = max(abs(q * pu), abs(st), 1.0)
            if abs(q * pu - st) <= max(2.0, 0.02 * m):
                sc += 5.0
            else:
                sc += 0.8
        if q > 1.02:
            sc += 1.2
        elif q > 0 and st > 0:
            sc += 0.3
    return sc


__all__ = [
    "extract_invoice_lines_from_word_geometry",
    "score_line_drafts",
]
