# Flux extraction facture (état avant pipeline v2)

## Mobile
- `POST /api/v1/invoices/scan` : multipart `image` + `transaction_type` → `invoice_id`, status `processing`.
- Polling `GET /api/v1/invoices/{id}` jusqu’à `ready`.
- `GET /api/v1/invoices/{id}/preview` : champs minimaux (`supplier_name`, `items[].designation|quantity|unit_price|line_total`, `totals`, `confidence`, `ocr_text`, `extraction_error`).
- Téléchargement PDF : `GET /api/v1/invoices/{id}/pdf`.

## Backend (historique)
- Tâche background `process_invoice_async` → `run_ocr_extract_pdf`.
- OCR : `ocr_service.extract_text(path)` → chaîne brute uniquement.
- Extraction : `invoice_extraction.extract_invoice_fields(ocr_text, tx)` (LLM + heuristiques + réconciliation).
- Normalisation : `normalize_extracted_invoice_dict` (totals imbriqués).
- PDF : `generate_invoice_report_pdf` attend clés « legacy » (`supplier_name`, `items` avec `designation`, `totals.htva|tva|ttc|timbre`).

## Points faibles corrigés par pipeline v2
- Pas de type `OCRResult` (lignes / mots / confiance).
- Pas d’endpoint synchrone `/invoices/extract` avec debug.
- Validation métier structurée et scoring champ par champ absents côté API.
- Pas de persistance des corrections utilisateur (`corrected_json`).

## Pipeline v2 (référence)
Voir modules `app/services/ocr/`, `invoice_global_pipeline.py`, `invoice_validation_service.py`, `confidence_scoring.py`.

### Endpoints API v1 (`/api/v1`)
- `GET /health` — alias versionné du health racine (base de données + version).
- `POST /invoices/extract` — multipart `image`, `transaction_type`, option `debug` (`true` / `false`) : pipeline synchrone **`InvoiceExtractionResponse`** (sans persistance ; fichier image temporaire supprimé).
- `POST /invoices/scan` — inchangé : job async ; `extracted_json` contient `extraction`, `validation`, `warnings`, `missing_fields`, `normalized_text`, `confidence`.
- `GET /invoices/{id}/preview` — champs enrichis : `warnings`, `missing_fields`, `field_confidence`, `global_confidence`, `validation`, `extraction`, `normalized_text`.
- `POST /invoices/{id}/apply_corrections` — JSON `{ "patch": { ... } }` (clés alignées sur le draft global) ; met à jour `corrected_json`, recalcule validation et aperçu.
- `POST /invoices/{id}/retry` — relance OCR + pipeline sur `image_path`.
- **Approve** : lecture des montants / fournisseur avec fusion `extraction` + `corrected_json`.

### Variables d’environnement (OCR / LLM / debug)
- `OCR_PROVIDER` — `paddleocr` | `tesseract` | `easyocr` | `auto` (défaut : `auto` = PaddleOCR puis Tesseract puis EasyOCR).
- `PADDLEOCR_LANG` — ex. `fr` (défaut), `en`, `ar` selon [doc PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR).
- `PADDLEOCR_USE_GPU` — `true` si GPU Paddle disponible.
- `LLM_PROVIDER` — `ollama` | `openai` | `groq` | `mcp` | …
- `INVOICE_PIPELINE_DEBUG` / `INVOICE_DEBUG` — si `1|true|yes`, active les champs `debug` côté traitement async (logs / extraits).
