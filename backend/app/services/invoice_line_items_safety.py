"""
Mode production sûr pour devis / offres tabulaires : ne pas exposer des lignes d’articles
automatiques comme fiables si la cohérence structurelle est insuffisante.

Les totaux, fournisseur, client et date restent extraits ; les lignes sont retirées de l’affichage
public et réservées au debug interne (INVOICE_PIPELINE_DEBUG).
"""
from __future__ import annotations

import copy
import os
from typing import Any

from app.services.invoice_user_messages import user_warnings_for_stored_invoice
from app.utils.money import to_float_safe

QUOTE_DOC_TYPES = frozenset({"quote", "devis", "quotation", "proforma"})

USER_MESSAGE_MANUAL_LINES = (
    "Les lignes du tableau nécessitent une vérification manuelle avant validation."
)

# Seuil confiance globale minimum pour accepter des lignes auto sur un devis
_MIN_GLOBAL_CONFIDENCE_QUOTE_LINES = 0.55


def _is_quote_like(document_type: str | None) -> bool:
    return (document_type or "").lower().strip() in QUOTE_DOC_TYPES


def _validation_flags_list(validation: dict[str, Any]) -> list[dict[str, Any]]:
    raw = validation.get("validation_flags") or []
    return [f for f in raw if isinstance(f, dict)]


def quote_line_items_trusted(stored: dict[str, Any]) -> bool:
    """
    True si les lignes du brouillon peuvent être traitées comme auto-extraites pour un devis.
    Les factures classiques ne passent pas par ces critères (toujours True).
    """
    ext = stored.get("extraction") or {}
    if not isinstance(ext, dict):
        return True
    if not _is_quote_like(ext.get("document_type")):
        return True
    items = ext.get("items") or []
    if not items:
        return True

    val = stored.get("validation") or {}
    if val.get("is_coherent_lines") is False:
        return False

    gc = to_float_safe(val.get("global_confidence"))
    if gc is not None and gc < _MIN_GLOBAL_CONFIDENCE_QUOTE_LINES:
        return False

    for f in _validation_flags_list(val):
        code = str(f.get("code") or "")
        if code.startswith("line_incoherent_"):
            return False

    sub = to_float_safe(ext.get("subtotal_amount")) or to_float_safe(stored.get("subtotal_htva"))
    line_sum = 0.0
    for it in items:
        if not isinstance(it, dict):
            continue
        lt = to_float_safe(it.get("line_subtotal"))
        if lt:
            line_sum += float(lt)
        q = to_float_safe(it.get("quantity"))
        if q is not None and (float(q) < 0 or float(q) > 1000):
            return False

    if sub and line_sum > 1.0:
        m = max(abs(float(sub)), line_sum, 1.0)
        if abs(line_sum - float(sub)) > max(5.0, 0.03 * m):
            return False

    return True


def apply_quote_line_items_safety(stored: dict[str, Any]) -> dict[str, Any]:
    """
    Pour devis à faible confiance ligne : vide `items` / `extraction.items`, marque la confiance,
    conserve les lignes brutes sous `pipeline.debug_suppressed_line_items` si debug activé.
    """
    if quote_line_items_trusted(stored):
        out = dict(stored)
        out.setdefault("line_items_trust", "auto")
        return out

    out = dict(stored)
    ext = dict(out.get("extraction") or {})
    items_snapshot = list(ext.get("items") or [])

    pipeline = dict(out.get("pipeline") or {})
    if os.getenv("INVOICE_PIPELINE_DEBUG", "").lower() in ("1", "true", "yes"):
        pipeline["debug_suppressed_line_items"] = copy.deepcopy(items_snapshot)
    out["pipeline"] = pipeline

    ext["items"] = []
    out["extraction"] = ext
    out["items"] = []

    val = dict(out.get("validation") or {})
    flags = list(val.get("validation_flags") or [])
    flags.append(
        {
            "code": "quote_lines_withheld_pending_review",
            "message": USER_MESSAGE_MANUAL_LINES,
            "severity": "warning",
        }
    )
    val["validation_flags"] = flags
    wset = set(val.get("warnings") or [])
    wset.add(USER_MESSAGE_MANUAL_LINES)
    val["warnings"] = sorted(wset)
    val["is_coherent_lines"] = None
    out["validation"] = val

    ws = list(out.get("warnings") or [])
    if USER_MESSAGE_MANUAL_LINES not in ws:
        ws.append(USER_MESSAGE_MANUAL_LINES)
    out["warnings"] = sorted(set(ws))

    out["line_items_trust"] = "manual_review_required"
    out["line_items_suppressed_reason"] = "quote_table_low_structural_confidence"

    out["user_warnings"] = user_warnings_for_stored_invoice(out)
    if USER_MESSAGE_MANUAL_LINES not in out["user_warnings"]:
        out["user_warnings"] = [USER_MESSAGE_MANUAL_LINES] + list(out["user_warnings"])

    return out


def apply_llava_visual_line_items_policy(stored: dict[str, Any]) -> dict[str, Any]:
    """
    Si la couche LLaVA demande une relecture manuelle, ne pas traiter le tableau comme fiable
    pour PDF / stockage (aligné sur le mode « manual_review_required » existant).
    """
    pipe = stored.get("pipeline")
    if not isinstance(pipe, dict):
        return stored
    pc = pipe.get("post_corrections")
    if not isinstance(pc, dict):
        return stored
    lv = pc.get("llava_visual")
    if not isinstance(lv, dict) or lv.get("skipped"):
        return stored
    if not lv.get("manual_review_required"):
        return stored

    ext = stored.get("extraction") if isinstance(stored.get("extraction"), dict) else {}
    items = ext.get("items") or []
    if not items:
        out = dict(stored)
        out["line_items_trust"] = out.get("line_items_trust") or "manual_review_required"
        out["line_items_suppressed_reason"] = out.get("line_items_suppressed_reason") or (
            "llava_visual_manual_review"
        )
        summary = str(lv.get("summary_for_user") or "").strip()
        if summary:
            ws = set(out.get("warnings") or [])
            ws.add(summary)
            out["warnings"] = sorted(ws)
            val = dict(out.get("validation") or {})
            vws = set(val.get("warnings") or [])
            vws.add(summary)
            val["warnings"] = sorted(vws)
            out["validation"] = val
        out["user_warnings"] = user_warnings_for_stored_invoice(out)
        return out

    out = dict(stored)
    ext = dict(out.get("extraction") or {})
    items_snapshot = list(ext.get("items") or [])

    pipeline = dict(out.get("pipeline") or {})
    if os.getenv("INVOICE_PIPELINE_DEBUG", "").lower() in ("1", "true", "yes"):
        pipeline["debug_suppressed_line_items_llava"] = copy.deepcopy(items_snapshot)
    out["pipeline"] = pipeline

    ext["items"] = []
    out["extraction"] = ext
    out["items"] = []

    val = dict(out.get("validation") or {})
    flags = list(val.get("validation_flags") or [])
    msg = str(lv.get("summary_for_user") or "").strip() or USER_MESSAGE_MANUAL_LINES
    flags.append(
        {
            "code": "llava_visual_manual_review",
            "message": msg,
            "severity": "warning",
        }
    )
    val["validation_flags"] = flags
    wset = set(val.get("warnings") or [])
    wset.add(msg)
    val["warnings"] = sorted(wset)
    val["is_coherent_lines"] = None
    out["validation"] = val

    ws = list(out.get("warnings") or [])
    if msg not in ws:
        ws.append(msg)
    out["warnings"] = sorted(set(ws))

    out["line_items_trust"] = "manual_review_required"
    out["line_items_suppressed_reason"] = "llava_visual_manual_review"

    out["user_warnings"] = user_warnings_for_stored_invoice(out)
    if msg not in out["user_warnings"]:
        out["user_warnings"] = [msg] + list(out["user_warnings"])
    return out


__all__ = [
    "USER_MESSAGE_MANUAL_LINES",
    "apply_llava_visual_line_items_policy",
    "apply_quote_line_items_safety",
    "quote_line_items_trusted",
]
