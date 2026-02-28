# ExpenseVoice Backend

## Quick start

### 1. Start PostgreSQL

From the **project root** (where `infra/` is):

```bash
cd infra
docker compose up -d
```

This starts Postgres on `localhost:5432` (user `postgres`, password `postgres`, DB `expensevoice`).

### 2. Backend env (optional)

Copy and edit if needed:

```bash
cd backend
cp .env.example .env
```

Default `.env.example` includes `DATABASE_URL`, `JWT_SECRET`, and seed users. If you don't have `.env`, the app uses defaults (see `app/core/config.py` and `app/core/seed.py`).

### 3. Install dependencies and run

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Check

- API: http://localhost:8000
- Health: http://localhost:8000/health → `{"status":"ok"}`
- Docs: http://localhost:8000/docs

### Login

Default seeded users (if seed ran):

- **Admin:** `admin@company.com` / `Admin12345!`
- **Director:** `director@company.com` / `Director12345!`

---

## If the backend "doesn't work"

| Symptom | Fix |
|--------|-----|
| `Connection refused` to database | Start Postgres: `cd infra && docker compose up -d` |
| `ModuleNotFoundError: No module named 'app'` | Run uvicorn from **inside** `backend/`: `cd backend` then `uvicorn app.main:app ...` |
| Port 8000 in use | Use another port: `uvicorn app.main:app --reload --port 8001` and set dashboard `VITE_API_BASE_URL=http://localhost:8001` |
| 401 on login | Restart backend so seed runs and creates default admin/director users |

---

## Security (production)

- **Rate limiting:** Sensitive endpoints are limited (e.g. 10/min for record and login). Uses in-memory store by default; set `REDIS_URL` for production if using slowapi with Redis.
- **CORS:** Set `CORS_ORIGINS=https://dashboard.abess.tn,https://app.abess.tn` (comma-separated). If unset, only localhost is allowed.
- **JWT:** Set `JWT_SECRET` and optionally `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60).
- **Audio:** `MAX_AUDIO_BYTES` (default 10MB), `AUDIO_RETENTION_DAYS` (default 90). Run `python3 scripts/cleanup_audio.py` from cron to delete old files.
- **Headers:** `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` are set by middleware.

---

## Production readiness (Part 3)

- **Health:** `GET /health` returns `{"status":"ok","database":"ok","version":"1.0.0"}`. Set `APP_VERSION` in env if needed.
- **Structured logging:** Logs are JSON with `timestamp`, `level`, `message`, `request_id`. Set `JSON_LOGS=false` for plain text.
- **Redis rate limiting:** Set `REDIS_URL=redis://localhost:6379` (or your Redis) so rate limits are shared across instances. Install `redis` if you use this.
- **Daily backup:** Run `python3 scripts/backup_db.py` from the backend directory. Use cron, e.g. daily at 2 AM:
  ```bash
  0 2 * * * cd /path/to/backend && python3 scripts/backup_db.py >> /var/log/expensevoice_backup.log 2>&1
  ```
  Env: `BACKUP_DIR` (default: `backend/backups`), `BACKUP_RETENTION_DAYS` (default: 30; 0 = keep all). For PostgreSQL, `pg_dump` must be on PATH.
