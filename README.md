# Fenix

Telegram bot + Mini App for «Феникс бистро»: menu, cart, ordering and order management for staff.

- `docs/` — specifications (BMAD / spec-driven development), decisions
- `backend/` — FastAPI API, Telegram bot, background worker
- `webapp/` — Telegram Mini App (React + TypeScript + Vite)
- `infra/` — Docker Compose, Caddy, monitoring

See [docs/decisions.md](docs/decisions.md) for agreed requirements.

## Branches

- `develop` — integration branch, every change goes through a PR, no deploy
- `release` — merging into it deploys to the VPS via CI/CD
