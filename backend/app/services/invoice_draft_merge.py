"""
Fusion brouillon LLM + heuristique : compléter les champs vides sans écraser le LLM,
puis réconciliation avec l’OCR (priorité aux montants / références visibles).
"""
from __future__ import annotations

from app.schemas.invoice_pipeline import InvoiceExtractionDraft
from app.utils.money import to_float_safe


def _is_blank_str(v: object) -> bool:
    return v is None or (isinstance(v, str) and not str(v).strip())


def _amount_missing(v: float | None) -> bool:
    return v is None or v <= 0


def _amount_absurd(llm_v: float | None, heur_v: float | None) -> bool:
    """Heuristique jugée plus fiable si le LLM sort un ordre de grandeur incohérent."""
    if llm_v is None:
        return False
    if llm_v <= 0:
        return True
    if llm_v > 99_000_000:
        return True
    if heur_v is not None and heur_v > 0:
        ratio = llm_v / heur_v if heur_v else 999
        if ratio > 80 or (ratio < 0.012 and llm_v > 1_000_000):
            return True
    return False


def merge_draft_with_heuristic(
    llm: InvoiceExtractionDraft,
    heur: InvoiceExtractionDraft,
) -> InvoiceExtractionDraft:
    """
    Priorité au LLM pour tout champ déjà renseigné.
    L'heuristique ne remplit que les trous (évite d'écraser fournisseur / N° / date avec un brouillon items-only).
    """
    a = llm.model_dump()
    b = heur.model_dump()

    out: dict = dict(a)

    str_keys = (
        "supplier_name",
        "supplier_full_name",
        "client_name",
        "invoice_number",
        "invoice_date",
        "payment_due_date",
        "client_tax_id",
        "client_city",
        "client_address",
        "supplier_tax_id",
        "supplier_phone",
        "supplier_address",
        "currency",
    )
    for k in str_keys:
        if _is_blank_str(out.get(k)) and not _is_blank_str(b.get(k)):
            out[k] = b[k]

    if (b.get("document_type") or "").strip() == "quote":
        out["document_type"] = "quote"
    elif _is_blank_str(out.get("document_type")):
        out["document_type"] = (b.get("document_type") or "invoice") or "invoice"

    if out.get("tax_rate_percent") is None and b.get("tax_rate_percent") is not None:
        out["tax_rate_percent"] = b["tax_rate_percent"]

    amt_keys = (
        "subtotal_amount",
        "tax_amount",
        "stamp_tax",
        "total_amount",
        "amount_paid",
        "remaining_due",
    )
    for k in amt_keys:
        if _amount_missing(out.get(k)) and not _amount_missing(b.get(k)):
            out[k] = b[k]

    if (not out.get("items")) and b.get("items"):
        out["items"] = list(b["items"])

    # Fusion listes informatives (sans dupliquer brutalement)
    dl = list(a.get("detected_labels") or [])
    for x in b.get("detected_labels") or []:
        if x not in dl:
            dl.append(x)
    out["detected_labels"] = dl

    mw = sorted({*(a.get("missing_fields") or []), *(b.get("missing_fields") or [])})
    out["missing_fields"] = mw

    ww = sorted({*(a.get("warnings") or []), *(b.get("warnings") or [])})
    out["warnings"] = ww

    return InvoiceExtractionDraft.model_validate(out)


def merge_llm_and_heuristic_invoice(
    llm: InvoiceExtractionDraft,
    heur: InvoiceExtractionDraft,
    ocr_text: str = "",
) -> tuple[InvoiceExtractionDraft, dict[str, str]]:
    """
    Stratégie hybride : base = merge classique, puis corrections si le LLM est vide,
    incohérent numériquement, ou contredit l’OCR pour le n° de facture.

    Retourne (draft, provenance_champs) pour debug (llm|heuristic|ocr_regex).
    """
    from app.services.invoice_extraction import _heur_find_invoice_number

    provenance: dict[str, str] = {}
    base = merge_draft_with_heuristic(llm, heur)
    a = base.model_dump()
    h = heur.model_dump()

    forced_inv = (_heur_find_invoice_number(ocr_text or "") or "").strip()
    cur_inv = (a.get("invoice_number") or "").strip()
    if forced_inv:
        if not cur_inv or cur_inv.upper() != forced_inv.upper():
            a["invoice_number"] = forced_inv
            provenance["invoice_number"] = "ocr_regex"
        else:
            provenance["invoice_number"] = "heuristic_agrees_ocr"

    amt_keys = (
        "subtotal_amount",
        "tax_amount",
        "stamp_tax",
        "total_amount",
        "amount_paid",
        "remaining_due",
    )
    for k in amt_keys:
        lv = to_float_safe(a.get(k))
        hv = to_float_safe(h.get(k))
        if _amount_missing(lv) and not _amount_missing(hv):
            a[k] = hv
            provenance[k] = provenance.get(k, "heuristic")
        elif not _amount_missing(lv) and not _amount_missing(hv) and _amount_absurd(lv, hv):
            a[k] = hv
            provenance[k] = "heuristic_override_absurd_llm"

    str_after_merge = (
        "supplier_name",
        "supplier_full_name",
        "client_name",
        "client_tax_id",
        "client_city",
        "client_address",
        "supplier_tax_id",
        "supplier_phone",
        "supplier_address",
        "invoice_date",
        "payment_due_date",
        "currency",
    )
    for k in str_after_merge:
        if _is_blank_str(a.get(k)) and not _is_blank_str(h.get(k)):
            a[k] = h[k]
            provenance[k] = "heuristic"

    if (not a.get("items")) and h.get("items"):
        a["items"] = list(h["items"])
        provenance["items"] = "heuristic"

    w = list(a.get("warnings") or [])
    if provenance:
        w.append("hybrid_merge_applied")
    a["warnings"] = sorted(set(w))

    ul = str(ocr_text or "").upper()
    if "DEVIS" in ul or "QUOTE" in ul or "PROPOSITION COMMERCIALE" in ul:
        if str(a.get("document_type") or "invoice").lower() in ("invoice", ""):
            a["document_type"] = "quote"
            provenance["document_type"] = "ocr_devis_hint"

    return InvoiceExtractionDraft.model_validate(a), provenance


def merge_llm_and_heuristic_document(
    llm_result: InvoiceExtractionDraft,
    heuristic_result: InvoiceExtractionDraft,
    ocr_text: str = "",
) -> tuple[InvoiceExtractionDraft, dict[str, str]]:
    """Alias explicite : même logique que `merge_llm_and_heuristic_invoice`."""
    return merge_llm_and_heuristic_invoice(llm_result, heuristic_result, ocr_text)
