---
title: 'Story 1.1: Модульный каркас бэкенда и контракт API'
type: 'refactor'
created: '2026-10-16'
status: 'ready-for-dev'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/implementation-artifacts/epic-1-context.md'
  - '{project-root}/docs/planning-artifacts/architecture/architecture-fenix-2026-10-16/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Код этапа 0 лежит плоско (`fenix/api`, `db.py`, `config.py`, `logging.py`), API без версии, клиент Mini App написан вручную — следующие истории начнут смешивать модули и расходиться с фронтендом.

**Approach:** Перестроить бэкенд по AD-1 (модули + `http/` + `platform/`), вынести бизнес-API под `/api/v1` с единым форматом ошибок, генерировать TS-клиент из OpenAPI и проверять в CI и границы модулей, и актуальность клиента. Поведение для гостя не меняется.

## Boundaries & Constraints

**Always:** `/api/health` и `/metrics` остаются по прежним путям; бот, воркер, миграции, Docker-образ и compose продолжают работать; mypy --strict и ruff проходят; модуль импортирует другой модуль только через `fenix.modules.<m>.api`; `platform` не импортирует модули.

**Never:** не добавлять таблицы и бизнес-логику модулей (они появятся в 1.2+); не трогать инфраструктуру стенда и `tg-egress`; не писать типы API вручную во фронтенде.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Health | `GET /api/health` | 200 `{"status":"ok"}` | — |
| Несуществующий роут v1 | `GET /api/v1/nope` | 404 `{"error":{"code":"not_found",...}}` | единый формат |
| Ошибка валидации | неверное тело запроса к роуту v1 | 422 `{"error":{"code":"validation_error","details":{...}}}` | единый формат |
| Необработанное исключение | исключение в обработчике | 500 `{"error":{"code":"internal_error"}}`, трейс в лог, не в ответ | единый формат |
| Нарушение границ | модуль импортирует `fenix.modules.x.models` | CI падает на проверке импортов | — |
| Устаревший клиент | схема API изменена, клиент не перегенерирован | CI падает на сравнении клиента | — |

</frozen-after-approval>

## Code Map

- `backend/src/fenix/config.py`, `db.py`, `logging.py` -- переносятся в `fenix/platform/` без изменения логики
- `backend/src/fenix/api/health.py` -- переносится в `fenix/http/health.py`
- `backend/src/fenix/main.py` -- фабрика `create_app`; подключение роутеров, lifespan; остаётся точкой входа (`fenix.main:create_app` в Dockerfile)
- `backend/src/fenix/telegram/webhook.py` и регистрация webhook в `main.py` -- удалить: по AD-8 webhook не используется, бот — отдельный polling-сервис; `BotMode.WEBHOOK` и связанные настройки убрать
- `backend/src/fenix/telegram/{bot,polling}.py`, `handlers/start.py` -- остаются адаптером, обновить импорты
- `backend/src/fenix/worker.py` -- остаётся (`fenix.worker:broker` в compose), обновить импорты
- `backend/migrations/env.py` -- импортирует `fenix.db` → `fenix.platform.db`
- `backend/tests/` -- обновить импорты; тест webhook удалить вместе с роутом
- `webapp/src/api/client.ts` -- ручной клиент заменить сгенерированным
- `.github/workflows/ci.yml` -- добавить шаги проверки импортов и актуальности клиента
- `infra/*` -- не менять

## Tasks & Acceptance

**Execution:**
- [ ] `backend/src/fenix/platform/{__init__,config,db,logging,errors}.py` -- перенос + обработчики ошибок в формат `{"error": {...}}` для HTTPException, RequestValidationError и Exception -- единый контракт ошибок
- [ ] `backend/src/fenix/http/{__init__,health,router}.py` -- health вне версии; `router.py` собирает `APIRouter(prefix="/api/v1")` из роутеров модулей -- точка подключения следующих историй
- [ ] `backend/src/fenix/modules/{identity,locations,catalog,ordering,payments,notifications,reporting}/{__init__,api}.py` -- пустые модули с docstring о владении данными -- структура AD-1/AD-2
- [ ] `backend/src/fenix/main.py`, `telegram/*`, `worker.py`, `migrations/env.py` -- новые импорты, удаление webhook -- работоспособность после переноса
- [ ] `backend/pyproject.toml` + `.importlinter` (контракты: модули независимы кроме `api`; `platform` не зависит от модулей и адаптеров) -- автоматическая защита границ
- [ ] `backend/src/fenix/http/openapi.py` + команда `fenix-openapi` -- выгрузка схемы OpenAPI в JSON без запуска сервера -- источник для генерации клиента
- [ ] `webapp/package.json`, `webapp/src/api/{schema.d.ts,client.ts}` -- `openapi-typescript` генерирует `schema.d.ts`, `client.ts` на `openapi-fetch` с заголовком `Authorization: tma …` -- типобезопасный клиент
- [ ] `.github/workflows/ci.yml` -- `lint-imports`; генерация клиента и `git diff --exit-code webapp/src/api/schema.d.ts` -- проверки из AC
- [ ] `backend/tests/test_errors.py`, `test_health.py` -- тесты матрицы I/O -- регрессия контракта

**Acceptance Criteria:**
- Given собранный образ API и compose стенда, when сервисы стартуют, then api, bot и worker поднимаются без ошибок импорта
- Given `uv run lint-imports`, when модули импортируют друг друга только через `api.py`, then проверка проходит
- Given Mini App, when выполняется `npm run build`, then сборка проходит с сгенерированным клиентом, health-запрос из `App.tsx` работает через него

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Design Notes

Генерация клиента: `fenix-openapi > webapp/openapi.json` → `openapi-typescript openapi.json -o src/api/schema.d.ts`. `openapi.json` не коммитится (артефакт), `schema.d.ts` коммитится — CI перегенерирует и сравнивает. `openapi-fetch` даёт `client.GET('/api/health')` с типами без кодогенерации методов.

## Verification

**Commands:**
- `cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest` -- expected: всё зелёное
- `cd webapp && npm run gen:api && git diff --exit-code src/api/schema.d.ts && npm run lint && npm run build` -- expected: без изменений и ошибок
- `docker compose -f infra/compose.dev.yaml up -d && cd backend && uv run alembic upgrade head` -- expected: миграции применяются из нового пути
