"""
Moteur d'extraction dynamique des tableaux (layout-aware).

Nommé `table_understanding` pour ne **pas** masquer le module `app.services.extraction`
(extraction achats / LLM).
"""

from __future__ import annotations

from app.services.table_understanding.dynamic_table_pipeline import run_dynamic_table_understanding

__all__ = ["run_dynamic_table_understanding"]
