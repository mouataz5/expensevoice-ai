"""Normalisation dict achat vocal (sans appel Groq)."""
from app.services.speech.voice_to_invoice_service import normalize_voice_purchase_dict


def test_normalize_recomputes_line_total():
    raw = {
        "type": "achat",
        "items": [
            {"name": "دجاج", "quantity": 50, "unit_price": 8600, "line_total": None},
            {"name": "قارورة غاز", "quantity": 1, "unit_price": 10, "line_total": 10},
        ],
        "total": None,
        "currency": "TND",
        "warnings": [],
    }
    out = normalize_voice_purchase_dict(raw)
    assert out["items"][0]["line_total"] == 50 * 8600
    assert out["total"] == 50 * 8600 + 10


def test_normalize_coerces_total_from_lines():
    raw = {
        "type": "achat",
        "items": [
            {"name": "x", "quantity": 2, "unit_price": 5, "line_total": 10},
        ],
        "total": 999,
        "currency": "TND",
        "warnings": [],
    }
    out = normalize_voice_purchase_dict(raw)
    assert out["total"] == 10
