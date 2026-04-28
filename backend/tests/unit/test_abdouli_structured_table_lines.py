"""Régression : devis Abdouli — grille structurée (11 lignes, totaux TN, pas de pollution adresse)."""
from __future__ import annotations

from app.services.invoice_facades.surya_table_extractor import (
    extract_invoice_lines_from_structured_metadata,
)
from app.utils.post_processing import (
    normalize_tunisia_supplier_phone,
    sanitize_client_address_block,
)


def _c(row: int, col: int, text: str, *, header: bool = False) -> dict:
    x0 = 12.0 + col * 130.0
    y0 = 20.0 + row * 30.0
    return {
        "row_id": row,
        "col_id": col,
        "text": text,
        "is_header": header,
        "bbox": [x0, y0, x0 + 115.0, y0 + 22.0],
    }


def _abdouli_table() -> dict:
    cells: list[dict] = [
        _c(0, 0, "Désignation", header=True),
        _c(0, 1, "UNITE", header=True),
        _c(0, 2, "QTE", header=True),
        _c(0, 3, "P.U", header=True),
        _c(0, 4, "P.HT", header=True),
        _c(0, 5, "P.TTC", header=True),
        _c(1, 0, "Transfo mono 50 kVA"),
        _c(1, 1, "UN"),
        _c(1, 2, "3"),
        _c(1, 3, "8 229.000"),
        _c(1, 4, "24 687.000"),
        _c(1, 5, ""),
        _c(2, 0, "Ferrures PR transfo mono (triplex)"),
        _c(2, 1, "UN"),
        _c(2, 2, "1"),
        _c(2, 3, "1 800.000"),
        _c(2, 4, "1 800.000"),
        _c(2, 5, ""),
        _c(3, 0, "Équipement BT poste aér triplex 50 kVA"),
        _c(3, 1, "UN"),
        _c(3, 2, "1"),
        _c(3, 3, "5 810.000"),
        _c(3, 4, "5 810.000"),
        _c(3, 5, ""),
        _c(4, 0, "Mise à terre transfo aér triph ou monop"),
        _c(4, 1, "UN"),
        _c(4, 2, "1"),
        _c(4, 3, "1 200.000"),
        _c(4, 4, "1 200.000"),
        _c(4, 5, ""),
        _c(5, 0, "Parafoudre 10 kA PR réseau 30 kV"),
        _c(5, 1, "UN"),
        _c(5, 2, "3"),
        _c(5, 3, "375.000"),
        _c(5, 4, "1 125.000"),
        _c(5, 5, ""),
        _c(6, 0, "Pylône en fer rond 13-1700"),
        _c(6, 1, "UN"),
        _c(6, 2, "1"),
        _c(6, 3, "6 590.000"),
        _c(6, 4, "6 590.000"),
        _c(6, 5, ""),
        _c(7, 0, "Plaque danger de mort PR support"),
        _c(7, 1, "UN"),
        _c(7, 2, "1"),
        _c(7, 3, "70.000"),
        _c(7, 4, "70.000"),
        _c(7, 5, ""),
        _c(8, 0, "Herse de dériv < 42,4 m câble 54,6"),
        _c(8, 1, "UN"),
        _c(8, 2, "1"),
        _c(8, 3, "571.000"),
        _c(8, 4, "571.000"),
        _c(8, 5, ""),
        _c(9, 0, "Bretelle d'ancrage PR 54,6 ALMELEC"),
        _c(9, 1, "UN"),
        _c(9, 2, "4"),
        _c(9, 3, "50.000"),
        _c(9, 4, "200.000"),
        _c(9, 5, ""),
        _c(10, 0, "Fus 3H PR 50 kVA mono (100/125 kVA tri)"),
        _c(10, 1, "UN"),
        _c(10, 2, "3"),
        _c(10, 3, "300.000"),
        _c(10, 4, "900.000"),
        _c(10, 5, ""),
        _c(11, 0, "Sectionneur fus complet (sans recharge)"),
        _c(11, 1, "UN"),
        _c(11, 2, "3"),
        _c(11, 3, "590.000"),
        _c(11, 4, "1 770.000"),
        _c(11, 5, ""),
    ]
    return {"cells": cells, "table_idx": 0, "page": 0}


def test_structured_abdouli_11_lines_and_totals():
    meta = {"provider": "paddle_structure", "structured_tables": [_abdouli_table()]}
    lines, dbg = extract_invoice_lines_from_structured_metadata(meta)
    assert dbg.get("applied_to_draft") is True
    assert len(lines) == 11
    s = sum(float(ln.line_subtotal or 0) for ln in lines)
    assert abs(s - 44723.0) < 0.05
    first = next(ln for ln in lines if "Transfo mono" in (ln.description or ""))
    assert first.quantity == 3.0
    assert abs(float(first.unit_price or 0) - 8229.0) < 0.01
    assert abs(float(first.line_subtotal or 0) - 24687.0) < 0.01


def test_sanitize_client_address_rejects_designation():
    assert sanitize_client_address_block("Désignation") is None
    assert sanitize_client_address_block("DESIGNATION UNITE QTE") is None
    assert sanitize_client_address_block("12 avenue Habib Bourguiba Tunis") is not None


def test_normalize_tunisia_phone_compact():
    assert normalize_tunisia_supplier_phone("98104.335") == "98.104.335"
    assert normalize_tunisia_supplier_phone("98.104.335") == "98.104.335"
