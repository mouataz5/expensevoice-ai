"""Enrichissement OCR avec cellules Surya (sans dépendance sur surya-ocr)."""
from __future__ import annotations

import os

import pytest

from app.services.invoice_facades.table_parser import enrich_raw_ocr_with_surya_tables


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("SURYA_APPEND_TABLE_CELLS", raising=False)


def test_enrich_appends_cells_when_surya_provider(monkeypatch):
    monkeypatch.setenv("SURYA_APPEND_TABLE_CELLS", "1")
    meta = {
        "provider": "surya",
        "surya_tables": [
            {"cells": [{"row_id": 0, "col_id": 0, "text": "ART"}, {"row_id": 0, "col_id": 1, "text": "100"}]},
        ],
    }
    out = enrich_raw_ocr_with_surya_tables("HEADER", meta)
    assert "HEADER" in out
    assert "SURYA_TABLE_CELLS" in out
    assert "ART" in out and "100" in out


def test_enrich_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("SURYA_APPEND_TABLE_CELLS", "0")
    meta = {"provider": "surya", "surya_tables": [{"cells": [{"text": "X"}]}]}
    assert enrich_raw_ocr_with_surya_tables("A", meta) == "A"


def test_enrich_off_by_default(monkeypatch):
    monkeypatch.delenv("SURYA_APPEND_TABLE_CELLS", raising=False)
    meta = {
        "provider": "surya",
        "surya_tables": [{"cells": [{"row_id": 0, "col_id": 0, "text": "X"}]}],
    }
    assert enrich_raw_ocr_with_surya_tables("BASE", meta) == "BASE"
