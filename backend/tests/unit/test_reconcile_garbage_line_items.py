"""reconcile_extracted_invoice_numbers ne doit pas écraser HT/TTC crédibles avec Σ lignes folles."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.invoice_extraction import reconcile_extracted_invoice_numbers

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "invoices"


def _bad_abdouli_like_items() -> list[dict]:
    """Même ordres de grandeur que rapport PDF corrompu (colonnes permutées)."""
    rows = [
        ("Transfo mono 50 kVA", 1_800_000.0),
        ("Ferrures PR transfo mono (triplex)", 229_000.0),
        ("Équipement BT poste aér triplex 50 kVA", 810_000.0),
        ("Mise à terre transfo aér triph ou monop", 125_000.0),
        ("Parafoudre 10 kA PR réseau 30 kV", 590_000.0),
        ("Pylône en fer rond 13-1700", 70_000.0),
        ("Plaque danger de mort PR support", 571_000.0),
        ("Herse de dériv", 238_000.0),
        ("Bretelle d'ancrage PR 54.6 ALMELEC", 900_000.0),
        ("Fus 3H PR 50 kVA mono", 590_000.0),
        ("Sectionneur fus complet (sans recharge)", 770_000.0),
    ]
    out: list[dict] = []
    for des, lt in rows:
        out.append(
            {
                "designation": des,
                "quantity": 1.0,
                "unit_price": lt,
                "line_total": lt,
            }
        )
    return out


def test_reconcile_restores_totals_from_ocr_when_line_sum_absurd_vs_ttc() -> None:
    ocr = (FIX / "abdouli_devis_ocr.txt").read_text(encoding="utf-8")
    ex = {
        "supplier_name": "Entreprise Abdouli",
        "items": _bad_abdouli_like_items(),
        "subtotal_htva": 6_693_000.0,
        "tax_amount": 8_407_070.0,
        "total_ttc": 53_137.07,
        "currency": "TND",
    }
    out = reconcile_extracted_invoice_numbers(ex, ocr_text=ocr, transaction_type="buy")
    assert float(out["subtotal_htva"]) == pytest.approx(44_723.0, rel=0, abs=2.0)
    assert float(out["total_ttc"]) == pytest.approx(53_137.07, rel=0, abs=2.0)
    assert float(out["tax_amount"]) == pytest.approx(8_407.07, rel=0, abs=0.05)
    assert out.get("invoice_number") == "DV-2025-042"
    assert len(out.get("items") or []) == 3


def test_reconcile_scales_insane_tax_while_keeping_plausible_ttc() -> None:
    ex = {
        "supplier_name": "X",
        "items": _bad_abdouli_like_items()[:3],
        "subtotal_htva": 44_723.0,
        "tax_amount": 8_407_070.0,
        "total_ttc": 53_137.07,
        "currency": "TND",
    }
    out = reconcile_extracted_invoice_numbers(ex, ocr_text="minimal", transaction_type="buy")
    assert float(out["tax_amount"]) == pytest.approx(8_407.07, rel=0, abs=0.05)
