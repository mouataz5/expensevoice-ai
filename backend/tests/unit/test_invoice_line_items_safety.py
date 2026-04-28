"""Mode sûr devis : lignes retirées si confiance structurelle insuffisante."""
from __future__ import annotations

from app.services.invoice_line_items_safety import (
    USER_MESSAGE_MANUAL_LINES,
    apply_quote_line_items_safety,
    quote_line_items_trusted,
)


def test_invoice_not_quote_always_trusted_path():
    stored = {
        "extraction": {
            "document_type": "invoice",
            "items": [{"quantity": 2, "unit_price": 50, "line_subtotal": 100}],
        },
        "validation": {"is_coherent_lines": False, "global_confidence": 0.2},
    }
    assert quote_line_items_trusted(stored) is True
    out = apply_quote_line_items_safety(stored)
    assert out.get("line_items_trust") == "auto"


def test_quote_incoherent_lines_suppressed():
    stored = {
        "extraction": {
            "document_type": "devis",
            "subtotal_amount": 1000.0,
            "items": [
                {
                    "description": "X",
                    "quantity": 3.0,
                    "unit_price": 10.0,
                    "line_subtotal": 9999.0,
                }
            ],
        },
        "validation": {
            "is_coherent_lines": False,
            "global_confidence": 0.9,
            "validation_flags": [],
            "warnings": [],
        },
        "items": [{"designation": "X", "quantity": 3, "unit_price": 10, "line_total": 9999}],
        "warnings": [],
        "pipeline": {},
    }
    assert quote_line_items_trusted(stored) is False
    out = apply_quote_line_items_safety(stored)
    assert out["line_items_trust"] == "manual_review_required"
    assert out["items"] == []
    assert (out.get("extraction") or {}).get("items") == []
    assert USER_MESSAGE_MANUAL_LINES in (out.get("user_warnings") or [])


def test_quote_coherent_keeps_items():
    stored = {
        "extraction": {
            "document_type": "devis",
            "subtotal_amount": 300.0,
            "items": [
                {
                    "description": "A",
                    "quantity": 3.0,
                    "unit_price": 100.0,
                    "line_subtotal": 300.0,
                }
            ],
        },
        "validation": {
            "is_coherent_lines": True,
            "global_confidence": 0.8,
            "validation_flags": [],
            "warnings": [],
        },
        "items": [{"designation": "A", "quantity": 3, "unit_price": 100, "line_total": 300}],
        "warnings": [],
        "pipeline": {},
    }
    assert quote_line_items_trusted(stored) is True
    out = apply_quote_line_items_safety(stored)
    assert len(out.get("items") or []) == 1
    assert out.get("line_items_trust") == "auto"
