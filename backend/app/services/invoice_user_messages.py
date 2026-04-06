"""Avertissements lisibles pour PDF / app (pas de dump technique)."""

from __future__ import annotations

import re
from typing import Any

_TECH_HINTS = (
    "llm_",
    "groq:",
    "openai:",
    "ollama:",
    "json_parse",
    "provider:",
    "hybrid_merge_applied",
    "ocr_devis_hint",
    "line_items_source:",
    "surya_line_sum",
    "heuristic_zero_fix",
    "math_lines_vs_subtotal:",
    "math_total_vs_lines:",
)

_USER_BY_CODE = {
    "invoice_number_suspicious": "Veuillez vérifier le numéro du document.",
    "invoice_date_invalid": "La date du document semble incorrecte ou incomplète.",
    "currency_missing": "La devise n’a pas été détectée clairement.",
    "line_math_inconsistent": "Une ou plusieurs lignes ne vérifient pas exactement qté × prix — contrôle recommandé.",
}

_USER_BY_SUBSTRING = (
    ("Ligne ", "Contrôlez les montants des lignes du tableau."),
    ("qté×PU", "Contrôlez les montants des lignes du tableau."),
)


def user_warnings_for_stored_invoice(stored: dict[str, Any]) -> list[str]:
    """Construit une liste courte, non technique, pour affichage client."""
    out: list[str] = []
    seen: set[str] = set()

    val = stored.get("validation") or {}
    for flag in val.get("validation_flags") or []:
        if not isinstance(flag, dict):
            continue
        if flag.get("severity") not in ("warning", "error"):
            continue
        code = flag.get("code")
        if isinstance(code, str) and code in _USER_BY_CODE:
            msg = _USER_BY_CODE[code]
            if msg not in seen:
                seen.add(msg)
                out.append(msg)
            continue
        msg = (flag.get("message") or "").strip()
        if _is_technical(msg) or len(msg) > 160:
            continue
        if msg and msg not in seen:
            seen.add(msg)
            out.append(msg)

    merge_msgs: list[str] = []
    ext = stored.get("extraction") or {}
    if isinstance(ext, dict):
        merge_msgs = list(ext.get("warnings") or [])
    merge_msgs.extend(list(stored.get("warnings") or []))
    for w in merge_msgs:
        if not isinstance(w, str):
            continue
        s = w.strip()
        if not s or _is_technical(s):
            continue
        if s == "hybrid_merge_applied":
            msg = "Certaines valeurs ont été harmonisées automatiquement avec le texte du document."
            if msg not in seen:
                seen.add(msg)
                out.append(msg)
            continue
        if len(s) > 140:
            continue
        for pref, repl in _USER_BY_SUBSTRING:
            if s.startswith(pref):
                if repl not in seen:
                    seen.add(repl)
                    out.append(repl)
                break
        else:
            if s not in seen:
                seen.add(s)
                out.append(s)

    return out[:12]


def _is_technical(s: str) -> bool:
    sl = s.lower()
    if any(h in sl for h in _TECH_HINTS):
        return True
    if re.search(r"\[pipeline\]|\btrace_id\b|stack", sl):
        return True
    return False
