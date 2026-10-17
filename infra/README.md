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
worker, tg-egress, Postgres, Redis, Garage (S3, photos at `/media/*`), Prometheus, Loki,
Alloy, Grafana (`/grafana`).

Garage needs no manual setup: the deploy generates its secrets in `/opt/fenix/.env`
(`GARAGE_RPC_SECRET`, `GARAGE_ADMIN_TOKEN`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `ALERTS_WEBHOOK_TOKEN`)
and `fenix-seed` in the `migrate` service creates the layout, the `media` bucket, the key
and website access through the admin API.

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

Public addresses are GitHub variables of the `production` environment; every deploy
writes them into `/opt/fenix/.env`:

- `SITE_ADDRESS` — what Caddy serves, e.g. `fenix.kitexp.ru, 84-54-56-12.sslip.io`
  (each host gets its own Let's Encrypt certificate as soon as its DNS points here);
- `SITE_DOMAIN` — the primary host (Grafana's public URL);
- `WEBAPP_URL` — what the bot's «Открыть меню» buttons open.

After the rollout the workflow runs `fenix-smoke "$WEBAPP_URL"` inside the API container:
it walks the guest path through the public URL with launch data signed by the bot
token and fails the deploy on any broken step.

## Monitoring and alerts

Grafana (`https://<site>/grafana/`) provisions the «Fenix — обзор» dashboard and the alert
rules from `infra/monitoring/grafana/provisioning/`: api, worker or bot down for 2 minutes,
Telegram unreachable through tg-egress, more than 2% of 5xx in 5 minutes, an outbox event
older than 5 minutes. Prometheus scrapes the API (`/metrics`), the worker (`:9101`) and the
bot (`:9102`).

Alerts go to Grafana's webhook contact point → `POST /api/internal/alerts` on the API (not
routed by Caddy, bearer `ALERTS_WEBHOOK_TOKEN`) → the outbox → the Telegram chat bound by a
staff member sending `/alerts` in that group. Until a chat is bound, alerts are only logged.
