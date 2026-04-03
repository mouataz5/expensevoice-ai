"""
Métriques de latence pipeline (OCR / LLM / post-traitement) pour logs structurés.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger("app.pipeline")


@contextmanager
def pipeline_stage(
    stage: str,
    *,
    component: str = "invoice_pipeline",
    invoice_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Iterator[None]:
    """
    Enregistre duration_ms une fois le bloc terminé (succès ou exception).
    Les clés sont compatibles avec StructuredFormatter (extra pass-through).
    """
    t0 = time.perf_counter()
    payload: dict[str, Any] = {
        "pipeline_stage": stage,
        "component": component,
    }
    if invoice_id:
        payload["invoice_id"] = str(invoice_id)
    if extra:
        payload.update(extra)
    try:
        yield
    finally:
        payload["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        logger.info("pipeline_timing", extra=payload)
