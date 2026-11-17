"""Backward-compatible import path. The extraction logic lives in app.services.extraction."""
from app.services.extraction import (  # noqa: F401
    EXTRACTION_JSON_SCHEMA,
    build_extraction_schema,
    extract_purchase_fields,
)
