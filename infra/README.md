# Infrastructure

## Local development

```bash
cp .env.example .env            # fill TELEGRAM_BOT_TOKEN (test bot)
docker compose -f infra/compose.dev.yaml up -d
cd backend && uv sync && uv run alembic upgrade head
uv run uvicorn fenix.main:create_app --factory --reload   # API on :8000
uv run fenix-bot-polling                                   # bot (polling)
cd webapp && npm install && npm run dev                    # Mini App on :5173
```

Telegram's test environment accepts plain-HTTP Mini App URLs, so locally
`WEBAPP_URL=http://127.0.0.1:5173` works without certificates.

## Production (VPS)

Stack: `compose.prod.yaml` — Caddy (HTTPS + Mini App static), API (bot webhook),
worker, Postgres, Redis, MinIO, Prometheus, Loki, Alloy, Grafana (`/grafana`).

One-time server setup:

1. Create `/opt/fenix` owned by the deploy user and put `.env` there
   (template: `infra/.env.example`, generate passwords with `openssl rand -hex 24`).
2. Add the CI deploy public key to the deploy user's `~/.ssh/authorized_keys`.
3. In GitHub → Settings → Environments → `production`, add secrets
   `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` (private key).

Deploy: merge `develop` → `release`. CI builds `ghcr.io/fenix-msk/fenix-api` and
`fenix-web`, uploads the stack definition to `/opt/fenix` and runs
`docker compose up -d`. Migrations run in the one-shot `migrate` service before the API starts.

Until a domain exists, `SITE_ADDRESS=84-54-56-12.sslip.io` gives a real
Let's Encrypt certificate for the server IP.
