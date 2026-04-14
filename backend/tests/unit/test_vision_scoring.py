"""Tests for vision scoring and pipeline integration."""
from __future__ import annotations

from app.schemas.invoice_pipeline import InvoiceExtractionDraft, InvoiceLineDraft
from app.services.invoice_pipeline_core import _score_vision_items


def _make_line(desc: str, qty: float, pu: float, sub: float) -> InvoiceLineDraft:
    return InvoiceLineDraft(
        description=desc, quantity=qty, unit_price=pu, line_subtotal=sub
    )


def test_vision_score_coherent_items():
    """Vision draft with coherent qty*pu=subtotal should score high."""
    draft = InvoiceExtractionDraft(
        items=[
            _make_line("Transfo", 3, 8229.0, 24687.0),
            _make_line("Ferrures", 1, 1800.0, 1800.0),
            _make_line("Équipement", 1, 5810.0, 5810.0),
        ],
        subtotal_amount=32297.0,
        tax_amount=6136.43,
        total_amount=38433.43,
    )
    score = _score_vision_items(draft, "")
    assert score >= 8.0, f"Expected high score, got {score}"


def test_vision_score_empty_items():
    draft = InvoiceExtractionDraft(items=[], global_confidence=0.0)
    score = _score_vision_items(draft, "")
    assert score == -1.0


def test_vision_score_garbage_items():
    """Items with qty*pu != subtotal should score lower."""
    draft = InvoiceExtractionDraft(
        items=[
            _make_line("Item1", 2, 100.0, 999999.0),
            _make_line("Item2", 0, 0, 50000.0),
        ],
        subtotal_amount=1000.0,
        total_amount=1190.0,
    )
    score = _score_vision_items(draft, "")
    assert score < 4.0, f"Expected low score for garbage, got {score}"


def test_vision_beats_structured_when_coherent():
    """When vision items match math, score should exceed typical structured."""
    vision = InvoiceExtractionDraft(
        items=[
            _make_line("A", 3, 8229.0, 24687.0),
            _make_line("B", 1, 1800.0, 1800.0),
            _make_line("C", 1, 5810.0, 5810.0),
            _make_line("D", 1, 1200.0, 1200.0),
            _make_line("E", 4, 50.0, 200.0),
        ],
        subtotal_amount=33697.0,
        tax_amount=6402.43,
        total_amount=40099.43,
    )
    v_score = _score_vision_items(vision, "")
    assert v_score >= 4.0, f"Vision score {v_score} should be >= 4.0 to be used"
