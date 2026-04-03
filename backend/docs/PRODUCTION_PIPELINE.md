# Pipeline production — plan et étapes

## Vue d’ensemble

Améliorations **progressives** : si une option n’est pas configurée, le comportement reste celui d’origine (FastAPI `BackgroundTasks`, un seul appel LLM, etc.).

| Étape | Fichiers / config | Activation |
|--------|-------------------|------------|
| **1. File d’attente** | `CELERY_BROKER_URL`, Redis, worker Celery | Définir `CELERY_BROKER_URL=redis://...` |
| **2. Post-processing** | `app/utils/post_processing.py`, déjà branché via `normalize_ocr_for_llm` | Toujours actif |
| **3. Observabilité** | `JSON_LOGS`, champs `duration_ms`, `pipeline_stage` | `JSON_LOGS=true` (défaut) |
| **4. Robustesse OCR** | `OCR_CHAIN_ROUNDS`, `OCR_PROVIDER_ATTEMPTS` | Variables optionnelles |
| **5. Fallback LLM** | `LLM_FALLBACK_PROVIDER` | Second provider si le premier échoue ou JSON invalide |
| **6. Cœur pipeline partagé** | `app/services/invoice_pipeline_core.py` | Refactor interne, API inchangée |

## Lancer Celery (dev)

```bash
# Terminal 1 — API
uvicorn app.main:app --reload

# Terminal 2 — Redis (ou docker run redis:7-alpine)
docker run -d -p 6379:6379 redis:7-alpine

# Terminal 3 — worker (même `DATABASE_URL` et secrets que l’API)
export CELERY_BROKER_URL=redis://localhost:6379/0
celery -A app.workers.celery_app worker -l INFO -Q invoice,voice
```

Avec `docker compose` dev : services `redis` et `celery-worker` (voir `docker-compose.yml`).

**Production** : `docker-compose.prod.yml` définit `CELERY_BROKER_URL` (défaut `redis://redis:6379/0`) sur `backend` et `celery-worker`, volume `/data` partagé pour les mêmes chemins que l’API.

## Variables utiles

- `CELERY_BROKER_URL` — si absent : file **inline** (`BackgroundTasks`) comme avant.
- `OCR_CHAIN_ROUNDS` — défaut `1` ; mettre `2` pour repasser toute la chaîne Paddle→Tesseract→EasyOCR une seconde fois si texte vide.
- `OCR_PROVIDER_ATTEMPTS` — défaut `2` : nouvelle tentative par provider après exception.
- `LLM_FALLBACK_PROVIDER` — ex. `ollama` ou `openai` (clés / URLs requises pour ce provider).

## Logs structurés (observabilité)

Avec `JSON_LOGS=true` (défaut dans `main.py`), les lignes JSON peuvent inclure :

| Champ | Signification |
|--------|----------------|
| `pipeline_stage` | `ocr_chain`, `ocr_provider`, `llm_extract`, `heuristic_merge`, `post_correct_validate`, `whisper` |
| `component` | `ocr`, `invoice_pipeline`, `stt` |
| `duration_ms` | Durée du segment |
| `invoice_id` | Présent sur le pipeline facture async quand connu |
| `method` / `path` / `status_code` | Middleware HTTP (déjà existant) |

Filtrer dans Loki / CloudWatch : `pipeline_stage="llm_extract"` ou `component="ocr"`.
