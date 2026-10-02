# Abes AgroTech — ExpenseVoice AI

Smart platform for agricultural sales, expenses, and invoice management.

---

## Production Deploy

Deploy with Docker Compose. Domains: **app.abesagrotech.tn** (frontend), **api.abesagrotech.tn** (backend).

### DNS

| Type | Name | Value   |
|------|------|---------|
| A    | app  | SERVER_IP |
| A    | api  | SERVER_IP |

### Prerequisites

- Docker and Docker Compose
- Optional: Certbot for HTTPS

### 1. Configure

```bash
cp .env.production.example .env.production
# Edit: POSTGRES_PASSWORD, JWT_SECRET, DATABASE_URL, CORS_ORIGINS=https://app.abesagrotech.tn
```

### 2. Run

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

- Frontend: http://app.abesagrotech.tn
- API: http://api.abesagrotech.tn
- Health: http://api.abesagrotech.tn/health

### 3. HTTPS (Certbot on host)

1. In `docker-compose.prod.yml`, nginx volumes use `certbot_www`. For host certbot, use a bind mount: `./certbot-www:/var/www/certbot:ro`, then `mkdir -p certbot-www`.
2. Get certs: `certbot certonly --webroot -w ./certbot-www -d app.abesagrotech.tn -d api.abesagrotech.tn`
3. Mount certs in nginx: add volume `/etc/letsencrypt:/etc/letsencrypt:ro`, uncomment `443:443`. Copy `nginx/conf.d/app.ssl.conf.example` and `api.ssl.conf.example` to `.conf`, uncomment and set `ssl_certificate` paths to `/etc/letsencrypt/live/.../fullchain.pem` and `privkey.pem`.
4. Restart: `docker compose -f docker-compose.prod.yml restart nginx`.
5. Renew: `certbot renew` then `docker compose ... exec nginx nginx -s reload`. Add to cron.

### 4. Deploy script

```bash
chmod +x scripts/deploy-prod.sh
./scripts/deploy-prod.sh
```

Pulls latest code, builds, and runs `up -d --build`.

### Volumes

- **db_data** — Postgres
- **redis_data** — Redis
- **app_data** — Audio, invoices, PDFs (`/data/audio`, `/data/invoices` in backend)

---

## Development

- Backend: `cd backend && uvicorn app.main:app --reload`
- Frontend: `cd dashboard && npm run dev`
