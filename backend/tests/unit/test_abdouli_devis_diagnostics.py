"""
Dévis Abdouli (grille réelle) : tests ciblés sur les défauts documentaires et le parsing millimes.

Réf. image / grille : totaux imprimés, P.T.T.C parfois sans point décimal, ligne « Fus »
incohérente (3 × 30 ≠ 900 au HT), TVA 19 % ≠ HT × 0,19, léger écart HT+TVA vs TTC imprimé.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.invoice_pipeline import InvoiceExtractionDraft, InvoiceLineDraft
from app.services.invoice_heuristics import detect_totals
from app.services.invoice_validation_service import validate_invoice_draft
from app.utils.money import normalize_tunisian_invoice_amount, parse_amount_token

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "invoices"

# Montants « pièges » tels qu’au bas de grille / colonnes P.T.T.C (OCR réel).
_ABDOULI_TRICKY_AMOUNTS: list[tuple[str, float]] = [
    ("29 377.530", 29377.530),
    ("2 142.000", 2142.000),
    ("6 913 900", 6913.900),  # sans point avant les millimes
    ("1 428.000", 1428.000),
    ("1 338.750", 1338.750),
    ("7 842.100", 7842.100),
    ("83 300", 83.300),  # lire 83,300 et non 83300
    ("679.490", 679.490),
    ("238.000", 238.000),
    ("1 071 000", 1071.000),  # typo fréquente sans point
    ("2 023.000", 2023.000),
    ("44 723.000", 44723.000),
    ("8 407.070", 8407.070),
    ("53 137.070", 53137.070),
]


@pytest.mark.parametrize("raw,expected", _ABDOULI_TRICKY_AMOUNTS)
def test_abdouli_tricky_tokens_parse(raw: str, expected: float) -> None:
    p = parse_amount_token(raw)
    n = normalize_tunisian_invoice_amount(raw)
    assert p == pytest.approx(expected, rel=0, abs=0.001)
    assert n == pytest.approx(expected, rel=0, abs=0.001)


def test_abdouli_full_grid_fixture_totals_heuristic() -> None:
    text = (FIX / "abdouli_devis_full_grid_ocr.txt").read_text(encoding="utf-8")
    t = detect_totals(text, None)
    assert t["subtotal_htva"] == pytest.approx(44723.0, abs=0.01)
    assert t["tax_amount"] == pytest.approx(8407.07, abs=0.02)
    assert t["total_ttc"] == pytest.approx(53137.07, abs=0.02)


def test_abdouli_naive_19pct_tva_differs_from_printed_tva() -> None:
    """Sur le document : TVA imprimée n’est pas HT × 19 % (arrondis / autre base)."""
    ht = 44723.0
    tva_printed = 8407.07
    naive = ht * 0.19
    assert abs(naive - tva_printed) > 80.0


def test_abdouli_ht_plus_tva_not_equal_to_printed_ttc() -> None:
    """Écart connu entre HT + TVA lignes de total et TTC imprimé (7 TND sur la ref. analysée)."""
    ht = 44723.0
    tva = 8407.07
    ttc = 53137.07
    assert abs((ht + tva) - ttc) == pytest.approx(7.0, abs=0.05)


def test_validation_flags_fus_line_qty_times_pu_vs_ht_subtotal() -> None:
    """Ligne type « Fus 3H » : 3 × 30.000 ≠ 900.000 imprimé au P.HT — doit être signalé."""
    draft = InvoiceExtractionDraft(
        document_type="quote",
        supplier_name="Entreprise Abdouli",
        invoice_number="DV-2025-042",
        invoice_date="2025-12-22",
        currency="TND",
        subtotal_amount=44723.0,
        tax_amount=8407.07,
        total_amount=53137.07,
        items=[
            InvoiceLineDraft(
                description="Fus 3H PR 50 kVA mono (erreur saisie document)",
                quantity=3.0,
                unit_price=30.0,
                line_subtotal=900.0,
            )
        ],
    )
    val = validate_invoice_draft(draft, "")
    assert val.is_coherent_lines is False
    codes = {f.code for f in (val.validation_flags or [])}
    assert any(c.startswith("line_incoherent_") for c in codes)
    assert any("qté×PU" in w for w in (val.warnings or []))


def test_abdouli_fixture_mentions_written_total_millimes() -> None:
    text = (FIX / "abdouli_devis_full_grid_ocr.txt").read_text(encoding="utf-8")
    assert "070 millimes" in text.lower() or "070 millime" in text.lower()
    assert "DV-2025-042" in text
