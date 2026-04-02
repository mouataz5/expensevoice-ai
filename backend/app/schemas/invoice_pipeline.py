"""
Types partagés pour le pipeline global OCR → LLM → validation → réponse API.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OCRWordSpan(BaseModel):
    text: str = ""
    confidence: float | None = None
    bbox: tuple[float, float, float, float] | None = None  # x0,y0,x1,y1 if known


class OCRLineSpan(BaseModel):
    text: str
    confidence: float | None = None
    words: list[OCRWordSpan] = Field(default_factory=list)


class OCRResult(BaseModel):
    raw_text: str
    lines: list[OCRLineSpan] = Field(default_factory=list)
    words: list[OCRWordSpan] = Field(default_factory=list)
    confidence: float | None = None  # agrégé si disponible
    metadata: dict[str, Any] = Field(default_factory=dict)


class InvoiceLineDraft(BaseModel):
    description: str | None = None
    details: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    line_subtotal: float | None = None


class InvoiceExtractionDraft(BaseModel):
    """Sortie attendue du LLM (schéma global)."""

    document_type: str = "invoice"
    supplier_name: str | None = None
    supplier_full_name: str | None = None
    client_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None  # YYYY-MM-DD ou null
    payment_due_date: str | None = None
    client_tax_id: str | None = None
    supplier_tax_id: str | None = None
    currency: str | None = None
    items: list[InvoiceLineDraft] = Field(default_factory=list)
    subtotal_amount: float | None = None
    tax_amount: float | None = None
    stamp_tax: float | None = None
    total_amount: float | None = None
    amount_paid: float | None = None
    remaining_due: float | None = None
    detected_labels: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    global_confidence: float = 0.0


class NormalizedAmounts(BaseModel):
    subtotal_amount: float | None = None
    tax_amount: float | None = None
    stamp_tax: float | None = None
    total_amount: float | None = None
    amount_paid: float | None = None
    remaining_due: float | None = None
    lines: list[dict[str, Any]] = Field(default_factory=list)


class ValidationFlag(BaseModel):
    code: str
    message: str
    severity: str = "info"  # info | warning | error


class InvoiceValidationResult(BaseModel):
    is_coherent_total: bool | None = None
    is_coherent_lines: bool | None = None
    likely_paid_in_full: bool | None = None
    validation_flags: list[ValidationFlag] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    normalized_amounts: NormalizedAmounts = Field(default_factory=NormalizedAmounts)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    global_confidence: float = 0.0


class InvoiceExtractionDebug(BaseModel):
    ocr_provider: str | None = None
    llm_provider: str | None = None
    normalized_text_excerpt: str | None = None
    system_prompt_excerpt: str | None = None
    user_prompt_excerpt: str | None = None
    llm_raw_response: str | None = None
    parsed_ok: bool = True
    validation_summary: str | None = None
    # Debug étendu (extraits longs — voir excerpt côté pipeline)
    raw_ocr_text: str | None = None
    cleaned_text_full: str | None = None
    system_prompt_full: str | None = None
    llm_raw_response_full: str | None = None
    final_json_text: str | None = None
    post_corrections: dict[str, Any] | None = None


class InvoiceExtractionResponse(BaseModel):
    success: bool = True
    ocr_text: str = ""  # brut OCR agrégé
    normalized_text: str = ""  # texte normalisé pour LLM (alias logique de cleaned_text)
    cleaned_text: str = ""  # identique à normalized_text dans le pipeline actuel
    data: InvoiceExtractionDraft
    validation: InvoiceValidationResult
    warnings: list[str] = Field(default_factory=list)
    debug: InvoiceExtractionDebug | None = None
    ocr_metadata: dict[str, Any] = Field(default_factory=dict)
    post_corrections: dict[str, Any] = Field(default_factory=dict)
