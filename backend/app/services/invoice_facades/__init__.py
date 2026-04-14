"""
Façades facture (Surya tables, header/client, etc.).

Le package s’appelle `invoice_facades` pour ne pas masquer `app.services.extraction`
(achats / LLM) ni `invoice_extraction.py`. Le moteur tableau dynamique vit dans
`app.services.table_understanding` pour la même raison.
"""

from __future__ import annotations
