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

Stack: `compose.prod.yaml` — Caddy (HTTPS + Mini App static), API, bot (polling),
worker, tg-egress, Postgres, Redis, MinIO, Prometheus, Loki, Alloy, Grafana (`/grafana`).

### Telegram egress

The VPS cannot reach Telegram directly. `tg-egress` runs an AmneziaWG client and a
SOCKS5 proxy (`socks5://tg-egress:1080`, internal network only); the backend sends
Bot API calls through it via `TELEGRAM_PROXY_URL`. Only Telegram subnets are routed
into the tunnel, everything else goes out directly.

The tunnel config lives only on the server: `/opt/fenix/tg-egress/awg0.conf`
(AmneziaWG 2.0 format, `AllowedIPs` = Telegram IPv4 ranges, no `DNS` line, no empty
`I*` parameters). Never commit it.

One-time server setup:

1. Create `/opt/fenix` owned by the deploy user and put `.env` there, plus the tunnel
   config at `/opt/fenix/tg-egress/awg0.conf` (mode 600)
   (template: `infra/.env.example`, generate passwords with `openssl rand -hex 24`).
2. Add the CI deploy public key to the deploy user's `~/.ssh/authorized_keys`.
3. In GitHub → Settings → Environments → `production`, add secrets
   `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` (private key).

Deploy: merge `develop` → `release`. CI builds `ghcr.io/fenix-msk/fenix-api` and
`fenix-web`, uploads the stack definition to `/opt/fenix` and runs
`docker compose up -d`. Migrations run in the one-shot `migrate` service before the API starts.

Until a domain exists, `SITE_ADDRESS=84-54-56-12.sslip.io` gives a real
Let's Encrypt certificate for the server IP.
