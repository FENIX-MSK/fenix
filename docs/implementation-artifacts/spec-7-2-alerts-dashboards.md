---
title: 'Story 7.2: Алерты и дашборды'
type: 'feature'
created: '2026-10-17'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/planning-artifacts/epics.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** О сбоях нужно узнавать раньше гостей.

**Approach:** Воркер (`:9101`) и бот (`:9102`) отдают метрики Prometheus: очередь outbox и возраст старейшего события, заказы по статусам, доступность Telegram через tg-egress (проба `getMe` раз в минуту). Grafana из provisioning: дашборд «Fenix — обзор» (сервисы, запросы и 5xx, p95, заказы по статусам, outbox) и правила: api/worker/bot недоступны > 2 мин, Telegram недоступен > 2 мин, 5xx > 2% за 5 мин, outbox старше 5 мин. Канал — webhook Grafana → `POST /api/internal/alerts` (токен, Caddy не пропускает) → outbox → чат, привязанный `/alerts`.

## Boundaries & Constraints

**Always:** алерты идут тем же путём через tg-egress с повторами; без привязанного чата — только в лог.

**Never:** прямого доступа Grafana к Telegram (с VPS он заблокирован).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Webhook без токена | — | — | 401 |
| Алерт | firing + resolved | «🔴 API недоступен — …», «✅ Outbox» в чат | повтор через outbox |
| `/alerts` гостем | — | «Привязать чат может только сотрудник кафе.» | — |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `platform/metrics.py`, метрики в `worker.py` и `telegram/polling.py`
- [x] `notifications/alerts.py` + миграция 0012, `/alerts` в боте
- [x] `http/alerts.py`, Caddy, `deploy.yml` (секрет, перезапуск мониторинга)
- [x] `infra/monitoring/*` -- scrape, дашборд, правила
- [x] тесты `test_alerts.py`

## Implementation Notes

- Агент принял решения сам.
- Отклонение: отдельный «Telegram-чат для алертов» привязывается командой `/alerts`, а не настройкой Grafana — с VPS Grafana не достучится до Telegram напрямую.

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | blind | `/api/internal/alerts` доступен снаружи через Caddy | high | `/api/*` проксируется целиком | patch: `respond 404` для `/api/internal/*` |
