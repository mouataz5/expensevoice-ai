"""
Extraction structurée des lignes d'articles depuis les grilles Surya (cellules row_id/col_id + bbox).

Ne remplace pas le fallback regex sur texte : le pipeline n'applique les lignes Surya que si
la détection de colonnes et un minimum de lignes valides sont satisfaits.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from statistics import median
from typing import Any, Literal

from app.schemas.invoice_pipeline import InvoiceLineDraft
from app.services.invoice_facades.table_correction_engine import (
    decide_manual_review,
    repair_row_assignment,
    validate_corrected_table,
)
from app.utils.money import normalize_tunisian_invoice_amount, to_float_safe

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

ROLE_ORDER_FOR_NUMERIC_FALLBACK = (
    "quantity",
    "unit_price",
    "line_ht",
    "line_ttc",
)

# line_ttc : éviter le motif « |ttc » seul (colonne « Total TTC » document confondu avec en-tête ligne)
_HEADER_PATTERNS: list[tuple[ColumnRole, re.Pattern[str]]] = [
    ("designation", re.compile(r"désign|designat|article|libell|libel|ref\.?\s*art|réf\.?\s*art|code\s*art|\bdes\.", re.I)),
    ("unit", re.compile(r"^\s*unit|condit|u\.|unite|unité|\bUN\b", re.I)),
    ("quantity", re.compile(r"qte|qté|quant|nombre|\bqty\b", re.I)),
    ("unit_price", re.compile(r"p\.?\s*u\b|^pu$|prix\s*unit|prix\s*u\.|unit\s*price", re.I)),
    ("line_ht", re.compile(r"p\.?\s*h\.?\s*t\b|^pht$|montant\s*ht|montant\s*h\.?\s*t(?!\s*va)", re.I)),
    (
        "line_ttc",
        re.compile(
            r"p\.[^\w]*t\.[^\w]*t\.[^\w]*c|p\.?\s*t\.?\s*t\.?\s*c\b|^pttc$|"
            r"montant\s*ttc|prix\s*ttc|p\.?\s*t\s*c\b(?!\s*document)",
            re.I,
        ),
    ),
]

_SKIP_ROW_DESC = re.compile(
    r"(?i)^(total|sous[-\s]?total|tva|timbre|net\s|arr[eê]t|^\s*$|"
    r"montant\s*lettre|mode\s*de\s*paiement)"
)

# Ligne d'objet / titre du devis (pas un article) — souvent extraite comme ligne à zéros.
_SKIP_SUBTITLE_ROW = re.compile(
    r"(?is)^(construction\s+poste\b|poste\s+3\s*x\s*50\s*kva\b|objet\s*du\s+devis\b|"
    r"objet\s*[:\s]|sujet\s*[:\s])",
)


@dataclass
class TableRowModel:
    """Modèle interne ligne tableau (avant mapping InvoiceLineDraft)."""

    description: str | None = None
    unit: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    line_ht: float | None = None
    line_ttc: float | None = None
    source_row_id: int | None = None


def _cell_x_center(cell: dict[str, Any]) -> float | None:
    bb = cell.get("bbox")
    if not bb or len(bb) < 4:
        return None
    try:
        x0, _, x1, _ = float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])
        return (x0 + x1) / 2
    except (TypeError, ValueError):
        return None


_MAX_SANE_QUANTITY = 1000.0


def _cell_y_center(cell: dict[str, Any]) -> float | None:
    bb = cell.get("bbox")
    if not bb or len(bb) < 4:
        return None
    try:
        y0, y1 = float(bb[1]), float(bb[3])
        return (y0 + y1) / 2.0
    except (TypeError, ValueError):
        return None


def _remap_row_ids_by_vertical_clusters(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Recalcule row_id depuis les bbox (même ligne ≈ même Y médian).
    Réduit les lignes mélangées quand Surya incrémente row_id hors ordre visuel.
    """
    if len(cells) < 4:
        return cells
    ycenters: list[float] = []
    for c in cells:
        yc = _cell_y_center(c)
        if yc is not None:
            ycenters.append(yc)
    if len(ycenters) < 4:
        return cells
    unique_y = sorted({round(y, 2) for y in ycenters})
    if len(unique_y) < 2:
        return cells
    gaps = [unique_y[i + 1] - unique_y[i] for i in range(len(unique_y) - 1)]
    med_gap = float(median(gaps)) if gaps else 16.0
    tol = max(7.0, med_gap * 0.42)

    bins: list[list[float]] = []
    for y in unique_y:
        placed = False
        for b in bins:
            cy = sum(b) / len(b)
            if abs(y - cy) <= tol:
                b.append(y)
                placed = True
                break
        if not placed:
            bins.append([y])
    centroids = sorted(sum(b) / len(b) for b in bins)

    def _row_for_y(y: float) -> int:
        return min(range(len(centroids)), key=lambda i: abs(centroids[i] - y))

    out: list[dict[str, Any]] = []
    for c in cells:
        cc = dict(c)
        yc = _cell_y_center(cc)
        if yc is not None:
            cc["row_id"] = _row_for_y(yc)
        out.append(cc)
    return out


def _remap_col_ids_by_horizontal_clusters(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Recalcule col_id depuis les bbox : même colonne ≈ même X médian (toutes lignes).

    Complète le recalage des lignes (_remap_row_ids_by_vertical_clusters) pour une grille
    (ligne, colonne) corrélée géométriquement, indépendamment des col_id parfois incohérents
    renvoyés par le moteur de table en amont.

    Tolérance adaptative : si une ligne contient N cellules mais le clustering ne produit que
    K<N colonnes (photo en perspective / grands écarts), on resserre la tolérance jusqu'à obtenir
    au moins N clusters — évite de fusionner P.U / P.H.T / P.T.T.C en une seule colonne.
    """
    if len(cells) < 4:
        return cells
    xcenters: list[float] = []
    for c in cells:
        xc = _cell_x_center(c)
        if xc is not None:
            xcenters.append(xc)
    if len(xcenters) < 4:
        return cells
    unique_x = sorted({round(x, 2) for x in xcenters})
    if len(unique_x) < 2:
        return cells
    gaps = [unique_x[i + 1] - unique_x[i] for i in range(len(unique_x) - 1)]
    med_gap = float(median(gaps)) if gaps else 24.0

    row_ids = {c["row_id"] for c in cells}
    max_cols_in_any_row = 1
    for rid in row_ids:
        max_cols_in_any_row = max(max_cols_in_any_row, sum(1 for c in cells if c["row_id"] == rid))
    target_clusters = min(max_cols_in_any_row, 14)

    def _centroids_for_tol(tol: float) -> list[float]:
        bins_c: list[list[float]] = []
        for x in unique_x:
            placed = False
            for b in bins_c:
                cx = sum(b) / len(b)
                if abs(x - cx) <= tol:
                    b.append(x)
                    placed = True
                    break
            if not placed:
                bins_c.append([x])
        return sorted(sum(b) / len(b) for b in bins_c)

    centroids: list[float] = []
    for frac in (0.50, 0.42, 0.35, 0.30, 0.25, 0.21, 0.18, 0.15, 0.125, 0.105, 0.09, 0.075, 0.06, 0.05):
        tol = max(2.0, med_gap * frac)
        centroids = _centroids_for_tol(tol)
        if len(centroids) >= target_clusters:
            break
    if len(centroids) < target_clusters:
        centroids = _centroids_for_tol(max(1.2, med_gap * 0.042))

    def _col_for_x(x: float) -> int:
        return min(range(len(centroids)), key=lambda i: abs(centroids[i] - x))

    out: list[dict[str, Any]] = []
    for c in cells:
        cc = dict(c)
        xc = _cell_x_center(cc)
        if xc is not None:
            cc["col_id"] = _col_for_x(xc)
        out.append(cc)
    return out


def _normalize_cells(table: dict[str, Any]) -> list[dict[str, Any]]:
    cells = table.get("cells") or []
    out: list[dict[str, Any]] = []
    for c in cells:
        if not isinstance(c, dict):
            continue
        try:
            rid = int(c["row_id"]) if c.get("row_id") is not None else -1
        except (TypeError, ValueError):
            rid = -1
        try:
            cid = int(c["col_id"]) if c.get("col_id") is not None else -1
        except (TypeError, ValueError):
            cid = -1
        if rid < 0 or cid < 0:
            continue
        txt = (c.get("text") or "").strip()
        out.append(
            {
                "row_id": rid,
                "col_id": cid,
                "text": txt,
                "bbox": c.get("bbox"),
                "is_header": bool(c.get("is_header")),
            }
        )
    # Grille conjointe : d’abord lignes (Y), puis colonnes (X) pour corréler les deux axes.
    out = _remap_row_ids_by_vertical_clusters(out)
    out = _remap_col_ids_by_horizontal_clusters(out)
    return out


def _median_x_by_col(cells: list[dict[str, Any]]) -> dict[int, float]:
    by_col: dict[int, list[float]] = {}
    for c in cells:
        xc = _cell_x_center(c)
        if xc is None:
            continue
        by_col.setdefault(c["col_id"], []).append(xc)
    return {cid: float(median(vs)) for cid, vs in by_col.items() if vs}


def _header_row_ids(cells: list[dict[str, Any]]) -> set[int]:
    hdr: set[int] = set()
    for c in cells:
        if c.get("is_header"):
            hdr.add(c["row_id"])
    if hdr:
        return hdr
    # Heuristique : première ligne = en-tête si elle contient des libellés typiques
    by_row: dict[int, list[str]] = {}
    for c in cells:
        by_row.setdefault(c["row_id"], []).append(c["text"])
    if not by_row:
        return set()
    min_row = min(by_row.keys())
    blob = " ".join(by_row[min_row]).lower()
    if any(p.search(blob) for _, p in _HEADER_PATTERNS):
        return {min_row}
    return set()


def _row_text_by_col(
    cells: list[dict[str, Any]], row_id: int
) -> dict[int, str]:
    parts: dict[int, list[str]] = {}
    for c in cells:
        if c["row_id"] != row_id:
            continue
        parts.setdefault(c["col_id"], []).append(c["text"])
    return {cid: " ".join(tx).strip() for cid, tx in parts.items()}


def detect_table_columns(
    table: dict[str, Any],
    *,
    cells: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Identifie le rôle de chaque col_id à partir de l'en-tête et des positions X.

    Retourne { "col_roles": {col_id: role}, "header_row_ids": [...], "col_x_order": [col_id...] }.
    """
    cell_list = cells if cells is not None else _normalize_cells(table)
    col_x = _median_x_by_col(cell_list)
    col_x_order = sorted(col_x.keys(), key=lambda k: col_x[k])
    header_ids = _header_row_ids(cell_list)
    col_roles: dict[int, ColumnRole] = {cid: "unknown" for cid in col_x_order}

    for hid in header_ids:
        by_col = _row_text_by_col(cell_list, hid)
        for cid, text in by_col.items():
            tl = text[:200]
            for role, pat in _HEADER_PATTERNS:
                if pat.search(tl):
                    prev = col_roles.get(cid, "unknown")
                    if prev == "unknown":
                        col_roles[cid] = role
                    break

    # Fallback positionnel : colonnes numériques non mappées de gauche à droite (hors désignation)
    unmapped = [cid for cid in col_x_order if col_roles.get(cid) == "unknown"]
    designation_candidates = [cid for cid, r in col_roles.items() if r == "designation"]
    if not designation_candidates and col_x_order:
        leftmost = col_x_order[0]
        col_roles[leftmost] = "designation"
        unmapped = [cid for cid in col_x_order if col_roles.get(cid) == "unknown"]

    # Première ligne de données pour classifier numérique vs texte
    data_rows = sorted({c["row_id"] for c in cell_list if c["row_id"] not in header_ids})
    sample_numeric: dict[int, bool] = {}
    if data_rows:
        sample = _row_text_by_col(cell_list, data_rows[0])
        for cid in unmapped:
            raw = sample.get(cid, "")
            v = normalize_tunisian_invoice_amount(raw) if raw else None
            sample_numeric[cid] = v is not None and abs(v) >= 0

    numeric_unmapped = [cid for cid in unmapped if sample_numeric.get(cid, False)]
    non_numeric_unmapped = [cid for cid in unmapped if cid not in numeric_unmapped]
    if non_numeric_unmapped and not designation_candidates:
        for cid in non_numeric_unmapped:
            if col_roles.get(cid) == "unknown":
                col_roles[cid] = "designation"
                break

    # Réappliquer l'ordre numérique standard sur les colonnes numériques restantes
    still_numeric = [
        cid
        for cid in col_x_order
        if col_roles.get(cid) == "unknown" and sample_numeric.get(cid, False)
    ]
    for i, role_name in enumerate(ROLE_ORDER_FOR_NUMERIC_FALLBACK):
        if i >= len(still_numeric):
            break
        col_roles[still_numeric[i]] = role_name

    return {
        "col_roles": {str(k): v for k, v in col_roles.items()},
        "header_row_ids": sorted(header_ids),
        "col_x_order": col_x_order,
    }


def _parse_numeric_cell(s: str) -> float | None:
    if not s or not str(s).strip():
        return None
    return normalize_tunisian_invoice_amount(str(s).strip())


def _parse_quantity_cell(text: str | None) -> float | None:
    """
    Quantité : éviter « 4.760 » (OCR colonnes) lu comme 4,76 — une marge + 3 chiffres = qté 1 chiffre.
    """
    if not text or not str(text).strip():
        return None
    raw = re.sub(r"\s+", "", str(text).strip())
    m1 = re.match(r"^(\d)\.(\d{3})$", raw)
    if m1:
        return float(int(m1.group(1)))
    v = _parse_numeric_cell(text)
    if v is None:
        v = to_float_safe(text)
    if v is not None and 0 < v <= 100_000:
        r = round(v)
        if abs(v - float(r)) < 0.051:
            return float(int(r))
    return v


def parse_surya_table_rows(
    table: dict[str, Any],
    *,
    column_info: dict[str, Any] | None = None,
) -> tuple[list[TableRowModel], list[str]]:
    """Reconstruit les lignes métier à partir d'une grille Surya normalisée."""
    cells = _normalize_cells(table)
    if len(cells) < 4:
        return [], ["too_few_cells"]

    col_meta = column_info or detect_table_columns(table, cells=cells)
    col_roles: dict[int, ColumnRole] = {}
    for k, v in (col_meta.get("col_roles") or {}).items():
        try:
            col_roles[int(k)] = v  # type: ignore[assignment]
        except (TypeError, ValueError):
            continue
    header_ids = set(col_meta.get("header_row_ids") or [])
    rows_out: list[TableRowModel] = []
    journal: list[str] = []

    all_rows = sorted({c["row_id"] for c in cells})
    for rid in all_rows:
        if rid in header_ids:
            continue
        by_col = _row_text_by_col(cells, rid)
        desc = None
        unit = None
        qty = pu = ht = ttc = None
        for cid, text in by_col.items():
            role = col_roles.get(cid, "unknown")
            if role == "designation":
                desc = text or None
            elif role == "unit":
                unit = text or None
            elif role == "quantity":
                qty = _parse_quantity_cell(text)
            elif role == "unit_price":
                pu = _parse_numeric_cell(text)
            elif role == "line_ht":
                ht = _parse_numeric_cell(text)
            elif role == "line_ttc":
                ttc = _parse_numeric_cell(text)

        d = (desc or "").strip()
        if not d and not any(x is not None for x in (qty, pu, ht, ttc)):
            continue
        if d and _SKIP_ROW_DESC.search(d):
            journal.append(f"skip_total_row_{rid}")
            continue
        if d and _SKIP_SUBTITLE_ROW.search(d):

            def _nil_money(x: Any) -> bool:
                return x is None or x == 0 or x == 0.0

            if _nil_money(qty) and _nil_money(pu) and _nil_money(ht) and _nil_money(ttc):
                journal.append(f"skip_subtitle_row_{rid}")
                continue

        rows_out.append(
            TableRowModel(
                description=d or None,
                unit=unit,
                quantity=qty,
                unit_price=pu,
                line_ht=ht,
                line_ttc=ttc,
                source_row_id=rid,
            )
        )
    return rows_out, journal


def _approx(a: float, b: float, *, tol_ratio: float = 0.02, tol_abs: float = 1.0) -> bool:
    m = max(abs(a), abs(b), 1.0)
    return abs(a - b) <= max(tol_abs, m * tol_ratio)


def _looks_like_price_value(x: float) -> bool:
    """Montant unitaire / prix (souvent > 1 avec décimales ou grand millier)."""
    if x <= 0:
        return False
    if x >= 150:
        return True
    fract = abs(x - round(x))
    return fract >= 0.02


def _maybe_swap_qty_unit_price(r: TableRowModel) -> tuple[TableRowModel, str | None]:
    """
    Qté colonne / prix colonne souvent permutés par OCR (ex. 6590 vs 1).
    On corrige si qté >> 1000, ou si qté×PU ≠ HT mais PU×qté == HT.
    """
    q, pu = r.quantity, r.unit_price
    if q is None or pu is None:
        return r, None
    qf, puf = float(q), float(pu)
    ht = float(r.line_ht) if r.line_ht is not None else None

    def prod_ok(a: float, b: float, h: float | None) -> bool:
        if h is None:
            return False
        return _approx(a * b, h, tol_ratio=0.02, tol_abs=max(2.0, abs(h) * 0.02))

    absurd_qty = qf > _MAX_SANE_QUANTITY or (
        qf > 50
        and puf <= _MAX_SANE_QUANTITY
        and _looks_like_price_value(qf)
        and not _looks_like_price_value(puf)
    )
    mismatch_fixed_by_swap = (
        ht is not None
        and not prod_ok(qf, puf, ht)
        and prod_ok(puf, qf, ht)
    )
    if absurd_qty or mismatch_fixed_by_swap:
        q_new = puf
        pu_new = qf
        if q_new <= 0 or pu_new <= 0:
            return r, None
        qty_out: float = round(q_new) if abs(q_new - round(q_new)) < 0.051 else round(q_new, 4)
        if qty_out > _MAX_SANE_QUANTITY:
            qty_out = round(q_new, 4)
        return (
            TableRowModel(
                description=r.description,
                unit=r.unit,
                quantity=qty_out,
                unit_price=round(pu_new, 6),
                line_ht=r.line_ht,
                line_ttc=r.line_ttc,
                source_row_id=r.source_row_id,
            ),
            "swapped_qty_unit_price",
        )
    return r, None


def validate_and_correct_rows(
    rows: list[TableRowModel],
) -> tuple[list[TableRowModel], list[str]]:
    """Cohérence qty × PU ≈ HT ; complète les champs manquants quand possible."""
    corrections: list[str] = []
    fixed: list[TableRowModel] = []
    for r in rows:
        r2, swap_note = _maybe_swap_qty_unit_price(r)
        if swap_note:
            corrections.append(f"row_{r.source_row_id}_{swap_note}")
        nr = TableRowModel(
            description=r2.description,
            unit=r2.unit,
            quantity=r2.quantity,
            unit_price=r2.unit_price,
            line_ht=r2.line_ht,
            line_ttc=r2.line_ttc,
            source_row_id=r2.source_row_id,
        )
        q, pu, ht = nr.quantity, nr.unit_price, nr.line_ht
        if q is not None and pu is not None and ht is not None:
            if not _approx(
                float(q) * float(pu),
                float(ht),
                tol_ratio=0.02,
                tol_abs=max(2.0, abs(float(ht)) * 0.02),
            ):
                for m in (10.0, 100.0, 1000.0, 10000.0):
                    p2 = float(pu) / m
                    if p2 <= 0:
                        continue
                    if _approx(
                        float(q) * p2,
                        float(ht),
                        tol_ratio=0.025,
                        tol_abs=max(2.0, abs(float(ht)) * 0.025),
                    ):
                        nr = TableRowModel(
                            description=nr.description,
                            unit=nr.unit,
                            quantity=nr.quantity,
                            unit_price=round(p2, 6),
                            line_ht=nr.line_ht,
                            line_ttc=nr.line_ttc,
                            source_row_id=nr.source_row_id,
                        )
                        pu = p2
                        corrections.append(f"row_{nr.source_row_id}_pu_rescale_div_{int(m)}")
                        break
            exp = round(float(q) * float(pu), 4)
            if not _approx(exp, float(ht), tol_ratio=0.02, tol_abs=max(2.0, abs(float(ht)) * 0.02)):
                if _approx(exp, float(ht), tol_ratio=0.06, tol_abs=5.0):
                    corrections.append(f"row_{nr.source_row_id}_line_ht_scaled_to_qty_pu")
                    nr.line_ht = round(exp, 3)
                else:
                    corrections.append(f"row_{nr.source_row_id}_line_ht_mismatch_kept")
        elif q is not None and pu is not None and ht is None:
            nr.line_ht = round(float(q) * float(pu), 3)
            corrections.append(f"row_{nr.source_row_id}_line_ht_inferred")
        elif q is not None and ht is not None and pu is None and float(q) != 0:
            nr.unit_price = round(float(ht) / float(q), 6)
            corrections.append(f"row_{nr.source_row_id}_unit_price_inferred")
        fixed.append(nr)
    return fixed, corrections


def _table_row_to_line_draft(r: TableRowModel) -> InvoiceLineDraft:
    details_parts: list[str] = []
    if r.unit:
        details_parts.append(f"unit:{r.unit}")
    if r.line_ttc is not None:
        details_parts.append(f"ttc:{r.line_ttc}")
    return InvoiceLineDraft(
        description=r.description,
        details="; ".join(details_parts) if details_parts else None,
        quantity=r.quantity,
        unit_price=r.unit_price,
        line_subtotal=r.line_ht,
    )


def _score_table(table: dict[str, Any]) -> tuple[int, int, int]:
    """
    Clé de tri (pour max) : (priorité_structurale, lignes_plausibles, nb_cellules).

    Priorité 0 = suspect « mini bloc totaux » (peu de lignes/colonnes, pas de colonne désignation).
    Priorité 1 = grille articles habituelle.
    """
    cells = _normalize_cells(table)
    if not cells:
        return 0, 0, 0
    info = detect_table_columns(table, cells=cells)
    col_roles = info.get("col_roles") or {}
    has_designation = any(v == "designation" for v in col_roles.values())
    row_ids = {c["row_id"] for c in cells}
    col_ids = {c["col_id"] for c in cells}
    n_rows = len(row_ids)
    n_cols = len(col_ids)
    mini_totals_suspect = (not has_designation) and n_rows <= 4 and n_cols <= 3
    structural_tier = 0 if mini_totals_suspect else 1

    rows, _j = parse_surya_table_rows(table, column_info=info)
    rows, _ = validate_and_correct_rows(rows)
    valid_lines = sum(
        1
        for r in rows
        if (r.description or "").strip()
        and (r.line_ht is not None or (r.quantity is not None and r.unit_price is not None))
    )
    return structural_tier, valid_lines, len(cells)


def _merge_surya_document_totals(
    metadata: dict[str, Any],
    document_hints: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fusionne totaux OCR Surya (si présents) et indices issus du brouillon facture (LLM + heuristique)."""
    out: dict[str, Any] = dict(metadata.get("surya_totals") or {})
    if not document_hints:
        return out
    for key in (
        "subtotal_amount",
        "subtotal_htva",
        "tax_amount",
        "total_amount",
        "total_ttc",
        "stamp_tax",
        "stamp_duty",
        "tax_rate_percent",
    ):
        v = document_hints.get(key)
        if v is not None:
            out[key] = v
    return out


def extract_invoice_lines_from_surya_metadata(
    metadata: dict[str, Any] | None,
    *,
    document_hints: dict[str, Any] | None = None,
) -> tuple[list[InvoiceLineDraft], dict[str, Any]]:
    """
    Point d'entrée pipeline : extrait des InvoiceLineDraft depuis metadata['surya_tables'].

    document_hints: totaux / taux TVA déjà détectés sur le brouillon (améliore scoring et validation).

    Retourne (lignes, debug dict) ; debug['applied_to_draft'] indique si le pipeline doit
    remplacer draft.items.
    """
    out_debug: dict[str, Any] = {
        "applied_to_draft": False,
        "reason": "no_surya_tables",
        "tables": [],
    }
    if not metadata or metadata.get("provider") != "surya":
        out_debug["reason"] = "not_surya_provider"
        return [], out_debug

    tables = metadata.get("surya_tables") or []
    if not tables:
        out_debug["reason"] = "empty_surya_tables"
        return [], out_debug

    best: dict[str, Any] | None = None
    best_score = (-1, -1, -1)
    best_idx = -1
    summaries: list[dict[str, Any]] = []
    for idx, tbl in enumerate(tables):
        if not isinstance(tbl, dict):
            continue
        sc = _score_table(tbl)
        summaries.append(
            {
                "table_idx": idx,
                "structural_tier": sc[0],
                "valid_line_score": sc[1],
                "n_cells": sc[2],
            }
        )
        if sc > best_score:
            best_score = sc
            best = tbl
            best_idx = idx

    out_debug["tables"] = summaries
    if not best or best_score[1] < 1:
        out_debug["reason"] = "no_usable_table"
        return [], out_debug

    cells = _normalize_cells(best)
    column_info = detect_table_columns(best, cells=cells)
    out_debug["best_table_idx"] = best_idx
    out_debug["column_detection"] = column_info

    rows, parse_journal = parse_surya_table_rows(best, column_info=column_info)
    out_debug["rows_before_validation"] = [r.__dict__ for r in rows]
    out_debug["parse_journal"] = parse_journal

    rows, val_journal = validate_and_correct_rows(rows)
    out_debug["corrections"] = val_journal
    out_debug["rows_after_validation"] = [r.__dict__ for r in rows]

    # Table correction engine: scoring + réparation par ligne, puis décision manual review.
    amount_vals: list[float] = []
    qty_vals: list[float] = []
    for r in rows:
        if r.unit_price is not None:
            amount_vals.append(float(r.unit_price))
        if r.line_ht is not None:
            amount_vals.append(float(r.line_ht))
        if r.line_ttc is not None:
            amount_vals.append(float(r.line_ttc))
        if r.quantity is not None:
            qty_vals.append(float(r.quantity))
    amount_vals = [x for x in amount_vals if x > 0]
    qty_vals = [x for x in qty_vals if x > 0]
    merged_totals = _merge_surya_document_totals(metadata, document_hints)
    tax_rate = merged_totals.get("tax_rate_percent")
    try:
        tax_rate_f = float(tax_rate) if tax_rate is not None else None
    except (TypeError, ValueError):
        tax_rate_f = None
    doc_ctx = {
        "row_stats": {
            "median_unit_price": float(median(amount_vals)) if amount_vals else None,
            "median_quantity": float(median(qty_vals)) if qty_vals else None,
        },
        "totals": merged_totals,
        "tax_rate_percent": tax_rate_f,
    }
    engine_rows: list[dict[str, Any]] = []
    corrected_rows: list[TableRowModel] = []
    for r in rows:
        rep = repair_row_assignment(r, doc_ctx)
        corrected_rows.append(rep["row"])
        engine_rows.append(
            {
                "source_row_id": r.source_row_id,
                "confidence": rep["confidence"],
                "second_best": rep["second_best"],
                "score_gap": rep["score_gap"],
                "auto_repaired": rep["auto_repaired"],
                "score_details": rep["score_details"],
            }
        )
    rows = corrected_rows

    table_validation = validate_corrected_table(rows, doc_ctx["totals"])
    manual_review_required = decide_manual_review(engine_rows, table_validation)
    out_debug["table_correction"] = {
        "rows": engine_rows,
        "global_validation": table_validation,
        "manual_review_required": manual_review_required,
        "corrected_count": sum(1 for r in engine_rows if r.get("auto_repaired")),
    }

    drafts: list[InvoiceLineDraft] = []
    for r in rows:
        if not (r.description or "").strip():
            if r.line_ht is None and not (r.quantity is not None and r.unit_price is not None):
                continue
        if (r.description or "").strip() and _SKIP_ROW_DESC.search((r.description or "").strip()):
            continue
        d = _table_row_to_line_draft(r)
        if d.line_subtotal is not None or (d.quantity is not None and d.unit_price is not None):
            drafts.append(d)

    if len(drafts) < 1:
        out_debug["reason"] = "no_valid_line_drafts"
        return [], out_debug

    line_sum_ht = sum(float(d.line_subtotal or 0) for d in drafts)
    try:
        sub_hint = None
        for k in ("subtotal_amount", "subtotal_htva"):
            v = merged_totals.get(k)
            if v is not None:
                sub_hint = float(v)
                break
    except (TypeError, ValueError):
        sub_hint = None
    if sub_hint is not None and sub_hint > 80 and line_sum_ht > 100:
        ratio = line_sum_ht / sub_hint
        if ratio > 2.75 or ratio < (1.0 / 2.75):
            out_debug["applied_to_draft"] = False
            out_debug["reason"] = "line_sum_vs_document_subtotal_mismatch"
            out_debug["line_sum_sanity"] = {
                "line_sum_ht": round(line_sum_ht, 3),
                "subtotal_hint": sub_hint,
                "ratio": round(ratio, 4),
            }
            return [], out_debug

    out_debug["applied_to_draft"] = True
    out_debug["reason"] = "ok"
    if manual_review_required and len(drafts) <= 1:
        # Cas très incertain: éviter d'injecter des lignes faibles dans le draft final.
        out_debug["applied_to_draft"] = False
        out_debug["reason"] = "manual_review_required"
        return [], out_debug
    out_debug["line_count"] = len(drafts)
    logger.info(
        "surya_table_extractor: using table %s with %d line items",
        best_idx,
        len(drafts),
    )
    return drafts, out_debug


__all__ = [
    "TableRowModel",
    "detect_table_columns",
    "parse_surya_table_rows",
    "validate_and_correct_rows",
    "extract_invoice_lines_from_surya_metadata",
]
