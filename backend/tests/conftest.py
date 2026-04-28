"""Pytest defaults so local runs match CI (strict tabular mode opt-in per test)."""
import os

# Tests that use OCR text without structured_tables must keep strict mode off unless they opt in.
os.environ.setdefault("INVOICE_STRICT_TABLE_EXTRACTION", "0")
os.environ.setdefault("OLLAMA_ENABLED", "0")
