"""
Fusion brouillon LLM + heuristique : compléter les champs vides sans écraser le LLM.
"""
from __future__ import annotations

from app.schemas.invoice_pipeline import InvoiceExtractionDraft


def _is_blank_str(v: object) -> bool:
    return v is None or (isinstance(v, str) and not str(v).strip())


def _amount_missing(v: float | None) -> bool:
    return v is None or v <= 0


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
        "supplier_tax_id",
        "currency",
    )
    for k in str_keys:
        if _is_blank_str(out.get(k)) and not _is_blank_str(b.get(k)):
            out[k] = b[k]

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
