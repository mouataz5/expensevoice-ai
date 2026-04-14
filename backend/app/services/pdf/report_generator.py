"""
Génération PDF rapports facture — façade sur `invoice_pdf.generate_invoice_report_pdf`.

Le rapport respecte `pipeline.post_corrections.dynamic_table` : en confiance tableau basse,
les lignes détaillées ne sont pas rendues (message de reprise manuelle), sans changer la signature.
"""
from __future__ import annotations

from app.services.invoice_pdf import generate_invoice_report_pdf

__all__ = ["generate_invoice_report_pdf"]
