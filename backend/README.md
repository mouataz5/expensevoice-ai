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
