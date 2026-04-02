"""Parsing JSON strict sortie LLM → InvoiceExtractionDraft."""

import pytest

from app.services.invoice_llm_extract import _parse_draft


def test_parse_flat_json() -> None:
    raw = (
        '{"document_type":"invoice","supplier_name":"ACME","items":[],'
        '"warnings":[],"missing_fields":[],"detected_labels":[],'
        '"field_confidence":{"supplier_name":0.9},"global_confidence":0.85}'
    )
    d = _parse_draft(raw)
    assert d.supplier_name == "ACME"
    assert d.global_confidence == pytest.approx(0.85)


def test_parse_nested_invoice_key() -> None:
    raw = (
        '{"invoice":{"document_type":"invoice","supplier_name":null,"items":[],'
        '"warnings":[],"missing_fields":[],"detected_labels":[],'
        '"field_confidence":{},"global_confidence":0.2}}'
    )
    d = _parse_draft(raw)
    assert d.document_type == "invoice"
    assert d.global_confidence == pytest.approx(0.2)


def test_parse_strips_fences_like_content() -> None:
    raw = 'noise {"document_type":"invoice","items":[],"warnings":[],"missing_fields":[],"detected_labels":[],"field_confidence":{},"global_confidence":0.1} tail'
    d = _parse_draft(raw)
    assert d.global_confidence == pytest.approx(0.1)

