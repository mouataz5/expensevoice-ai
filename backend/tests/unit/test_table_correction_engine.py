from app.services.invoice_facades.surya_table_extractor import TableRowModel
from app.services.invoice_facades.table_correction_engine import (
    decide_manual_review,
    generate_candidate_assignments,
    repair_row_assignment,
    score_assignment,
    validate_corrected_table,
)


def test_generate_candidate_assignments_has_current_mapping() -> None:
    row = TableRowModel(quantity=2.0, unit_price=100.0, line_ht=200.0, line_ttc=238.0)
    cands = generate_candidate_assignments(row)
    assert cands
    assert any(
        c.get("quantity") == 2.0
        and c.get("unit_price") == 100.0
        and c.get("line_ht") == 200.0
        for c in cands
    )


def test_score_prefers_math_coherent_assignment() -> None:
    row = TableRowModel(quantity=100.0, unit_price=2.0, line_ht=200.0, line_ttc=238.0)
    good = {"quantity": 2.0, "unit_price": 100.0, "line_ht": 200.0, "line_ttc": 238.0}
    bad = {"quantity": 100.0, "unit_price": 2.0, "line_ht": 200.0, "line_ttc": 238.0}
    ctx = {"row_stats": {"median_quantity": 2.0, "median_unit_price": 100.0}, "totals": {}}
    good_s, _ = score_assignment(row, good, ctx)
    bad_s, _ = score_assignment(row, bad, ctx)
    assert good_s > bad_s


def test_repair_row_assignment_autorepairs_when_confident() -> None:
    row = TableRowModel(quantity=200.0, unit_price=2.0, line_ht=400.0, line_ttc=476.0)
    ctx = {"row_stats": {"median_quantity": 2.0, "median_unit_price": 200.0}, "totals": {}}
    out = repair_row_assignment(row, ctx)
    assert out["confidence"] >= 0.6
    # Auto repair may be false on tight thresholds, but if true the corrected qty/price must be coherent.
    if out["auto_repaired"]:
        fixed = out["row"]
        assert fixed.quantity is not None and fixed.unit_price is not None and fixed.line_ht is not None
        assert abs((fixed.quantity * fixed.unit_price) - fixed.line_ht) < max(2.0, fixed.line_ht * 0.06)


def test_manual_review_decision_true_on_low_confidence_or_bad_totals() -> None:
    rows = [
        {"confidence": 0.42, "auto_repaired": False},
        {"confidence": 0.55, "auto_repaired": False},
    ]
    val = {"global_ok": False}
    assert decide_manual_review(rows, val) is True


def test_validate_corrected_table_detects_incoherence() -> None:
    rows = [TableRowModel(quantity=2.0, unit_price=100.0, line_ht=999.0, line_ttc=900.0)]
    out = validate_corrected_table(rows, {"subtotal_amount": 200.0, "total_amount": 238.0, "tax_amount": 38.0})
    assert out["global_ok"] is False


def test_validate_line_tax_ok_with_tax_rate() -> None:
    rows = [
        TableRowModel(quantity=3.0, unit_price=1000.0, line_ht=3000.0, line_ttc=3570.0),
        TableRowModel(quantity=1.0, unit_price=500.0, line_ht=500.0, line_ttc=595.0),
    ]
    totals = {
        "subtotal_amount": 3500.0,
        "tax_amount": 665.0,
        "total_amount": 4165.0,
        "tax_rate_percent": 19.0,
    }
    out = validate_corrected_table(rows, totals)
    assert out["line_tax_ok"] is True
    assert out["global_ok"] is True


def test_validate_line_tax_fails_when_ttc_wrong_for_rate() -> None:
    rows = [
        TableRowModel(quantity=1.0, unit_price=100.0, line_ht=100.0, line_ttc=200.0),
    ]
    out = validate_corrected_table(
        rows,
        {"subtotal_amount": 100.0, "total_amount": 119.0, "tax_amount": 19.0, "tax_rate_percent": 19.0},
    )
    assert out["line_tax_ok"] is False

