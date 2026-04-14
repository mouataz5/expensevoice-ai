"""Fumée production : devis Abdouli (fichier image de référence + montants ambigus)."""
from __future__ import annotations

from pathlib import Path

import pytest

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "invoices"


def test_devis_abdouli_reference_png_fixture_exists() -> None:
    assert (FIX / "devis_abdouli_reference.png").is_file()


@pytest.mark.integration
def test_ocr_devis_abdouli_reference_png_smoke() -> None:
    """Exige Paddle/Surya/Tesseract opérationnel ; sinon skip (CI minimal)."""
    from app.services.ocr.ocr_orchestrator import run_ocr

    png = FIX / "devis_abdouli_reference.png"
    if not png.is_file():
        pytest.skip("devis_abdouli_reference.png absent")
    res = run_ocr(str(png))
    raw = (res.raw_text or "").strip()
    if len(raw) < 80:
        pytest.skip("aucun OCR texte — installer un provider (paddleocr / surya / tesseract)")
    ul = raw.upper()
    assert "DEVIS" in ul or "ABDOULI" in ul or "BOUZID" in ul
