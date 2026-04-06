"""
Génération PDF rapports facture — façade sur `invoice_pdf.generate_invoice_report_pdf`.

Conserve un point d’entrée `services/pdf/` distinct de l’implémentation historique.
"""
from __future__ import annotations

from app.services.invoice_pdf import generate_invoice_report_pdf

__all__ = ["generate_invoice_report_pdf"]
