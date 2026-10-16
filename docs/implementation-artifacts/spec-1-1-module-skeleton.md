---
title: 'Story 1.1: Модульный каркас бэкенда и контракт API'
type: 'refactor'
created: '2026-10-16'
status: 'done'
baseline_commit: '86892134fb4d0e7145751f15f551e1d5183e5e7b'
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
- [x] `backend/src/fenix/platform/{__init__,config,db,logging,errors}.py` -- перенос + обработчики ошибок в формат `{"error": {...}}` для HTTPException, RequestValidationError и Exception -- единый контракт ошибок
- [x] `backend/src/fenix/http/{__init__,health,router}.py` -- health вне версии; `router.py` собирает `APIRouter(prefix="/api/v1")` из роутеров модулей -- точка подключения следующих историй
- [x] `backend/src/fenix/modules/{identity,locations,catalog,ordering,payments,notifications,reporting}/{__init__,api}.py` -- пустые модули с docstring о владении данными -- структура AD-1/AD-2
- [x] `backend/src/fenix/main.py`, `telegram/*`, `worker.py`, `migrations/env.py` -- новые импорты, удаление webhook -- работоспособность после переноса
- [x] `backend/pyproject.toml` + `.importlinter` (контракты: модули независимы кроме `api`; `platform` не зависит от модулей и адаптеров) -- автоматическая защита границ
- [x] `backend/src/fenix/http/openapi.py` + команда `fenix-openapi` -- выгрузка схемы OpenAPI в JSON без запуска сервера -- источник для генерации клиента
- [x] `webapp/package.json`, `webapp/src/api/{schema.d.ts,client.ts}` -- `openapi-typescript` генерирует `schema.d.ts`, `client.ts` на `openapi-fetch` с заголовком `Authorization: tma …` -- типобезопасный клиент
- [x] `.github/workflows/ci.yml` -- `lint-imports`; генерация клиента и `git diff --exit-code webapp/src/api/schema.d.ts` -- проверки из AC
- [x] `backend/tests/test_errors.py`, `test_health.py` -- тесты матрицы I/O -- регрессия контракта

**Acceptance Criteria:**
- Given собранный образ API и compose стенда, when сервисы стартуют, then api, bot и worker поднимаются без ошибок импорта
- Given `uv run lint-imports`, when модули импортируют друг друга только через `api.py`, then проверка проходит
- Given Mini App, when выполняется `npm run build`, then сборка проходит с сгенерированным клиентом, health-запрос из `App.tsx` работает через него

## Implementation Notes

- API больше не создаёт `Bot`: он был нужен только для webhook. `create_app` настраивает логи и lifespan, а сборка роутов и обработчиков вынесена в `build_app()` без настроек — её использует `fenix-openapi`, поэтому выгрузка схемы не требует `TELEGRAM_BOT_TOKEN`.
- Обработчики ошибок передаются через `FastAPI(exception_handlers=...)` (типизированы под mypy --strict). Добавлен `ApiError(status, code, message, details)` для доменных ошибок следующих историй (`order_conflict`, `unauthorized`); код для `HTTPException` выводится из HTTP-фразы (`not_found`, `method_not_allowed`).
- Роутер `/api/v1` объявляет ответы `4XX`/`5XX` моделью `ErrorResponse`: это заменяет в OpenAPI стандартную схему 422 FastAPI, и сгенерированный клиент типизирует ошибки по единому формату.
- import-linter 2.15: три контракта (независимость модулей кроме `api`; адаптеры — только через `api`; `platform` — нижний слой). Пока `api.py` пустые, ignore-правила ничего не матчат, поэтому `unmatched_ignore_imports_alerting = none`. Нарушения всех трёх контрактов проверены вручную пробными импортами.
- `openapi-typescript` 7.13 объявляет peer `typescript ^5`, в проекте TS 6 — закрыто `overrides` в `package.json` (генерация на TS 6 работает), `npm ci` в CI без флагов.
- Строки матрицы «Нарушение границ» и «Устаревший клиент» проверяются шагами CI (`lint-imports`, `git diff --exit-code`); оба сценария воспроизведены локально (пробное нарушение импорта, изменение схемы Health).
- Локально нет buildx и недоступен ghcr.io, поэтому репозиторный Dockerfile не собирался; AC про образ проверен эквивалентным образом на `python:3.14-slim` с тем же uv: `alembic upgrade head`, api (health/404/metrics), worker стартуют; bot доходит до сетевого вызова Telegram без ошибок импорта.
- `infra/*` не менялся: в `infra/caddy/Caddyfile` остался маршрут `/telegram/webhook`, в `infra/.env.example` — `PUBLIC_BASE_URL`/`TELEGRAM_WEBHOOK_SECRET`, в `compose.prod.yaml` — комментарий про `TELEGRAM_BOT_MODE`; лишние переменные игнорируются настройками (`extra="ignore"`).

## Spec Change Log

## Review Triage Log

Слои ревью (blind-hunter, edge-case-hunter, verification-gap) выполнены inline в основной сессии: субагенты в этом проекте запускаются только по явной просьбе пользователя.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | blind | Контракты import-linter не запрещают модулям импортировать адаптеры (`http`, `telegram`, `main`) и aiogram (AD-1, AD-8) | medium | Пробный `import fenix.http.router` и `import aiogram` в модуле проходили проверку | patch: контракт `modules-below-adapters`, `include_external_packages`; оба нарушения теперь ломают проверку |
| 2 | verification-gap | Замена схемы 422 на `ErrorResponse` в OpenAPI ничем не проверена | medium | Тестов на `responses` роутера v1 не было; при написании теста выяснилось, что тестовый роутер подключался мимо `api_v1` | patch: `test_v1_errors_documented_with_uniform_schema`, probe подключается через `api_v1` |
| 3 | edge-case | Код ошибки из HTTP-фразы не всегда snake_case: 418 → `i'm_a_teapot` | low | Воспроизведено тестом; `replace` не убирал апостроф | patch: нормализация `re.sub(r"[^a-z0-9]+", "_")` |
| 4 | edge-case | `HTTPException` с `detail`-словарём теряет детали (в `message` уходит код) | low | Тело было `details: {}` при `detail={"pot": "full"}` | patch: dict-`detail` кладётся в `details`, тест `test_http_exception_dict_detail_goes_to_details` |
| 5 | verification-gap | Импорты `migrations/env.py` не проверяются в CI (mypy охватывает только пакет `fenix`) | medium | Ошибка импорта в env.py прошла бы все шаги CI | patch: `test_migrations_env_loads_offline` (`alembic upgrade head --sql`) |
| 6 | verification-gap | `test_openapi_schema_needs_no_settings` локально проходит ложно: `../.env` с токеном доступен из рабочего каталога | low | `.env` лежит в корне репозитория, `Settings` читает `../.env` | patch: `monkeypatch.chdir(tmp_path)` |
| 7 | verification-gap | Сохранение заголовка `Allow` у 405 не проверено | low | Тест проверял только код | patch: проверка `allow == "POST"` |
| 8 | blind | Нет документации по `gen:api` для разработчиков Mini App | low | `webapp/README.md` не упоминал генерацию клиента | patch: раздел в README |
| 9 | blind | Трейс необработанного исключения пишется дважды: JSON `http.unhandled_error` и строка uvicorn «Exception in ASGI application» | low | Воспроизведено на uvicorn; Starlette `ServerErrorMiddleware` всегда перевыбрасывает исключение после обработчика, подавить из обработчика нельзя | defer: решается вместе с выводом логов uvicorn через structlog (сейчас access/error-логи uvicorn идут мимо JSON) |
| 10 | blind | Caddy по-прежнему проксирует `/telegram/webhook` на API, где маршрута больше нет | low | `infra/caddy/Caddyfile:7`; запрос получит 404 | defer: intent запрещает трогать инфраструктуру стенда |
| 11 | blind | Устаревшие упоминания webhook в `infra/.env.example` и комментарии `compose.prod.yaml` | low | Переменные игнорируются (`extra="ignore"`), но вводят в заблуждение | defer: та же граница по infra |
| 12 | blind | `fenix-bot-polling` при каждом старте вызывает `delete_webhook(drop_pending_updates=True)` и теряет сообщения гостей, пришедшие во время рестарта бота | medium | Существовало до истории (`telegram/polling.py`), теперь polling — единственный режим и в проде | defer: поведение не вводилось этой историей |
| 13 | blind | Валидационные `details.errors` возвращают клиенту поле `input` с его же данными | false | Совпадает с поведением FastAPI по умолчанию; данные уходят только отправителю и не логируются | reject |
| 14 | blind | `uv run` в `gen:api` без `--locked` может молча перезаписать `uv.lock` | false | Расхождение lock-файла валит backend-джоб CI (`uv sync --locked`) раньше, чем это станет проблемой | reject |
| 15 | edge-case | Контракт адаптеров разрешает импорт пакета `fenix.modules.<m>` (его `__init__`) | low | Сейчас `__init__` содержат только docstring; обход возможен лишь при реэкспорте внутренностей в `__init__` | reject: маловероятно, а закрытие требует дополнительных правил |

## Design Notes

Генерация клиента: `fenix-openapi > webapp/openapi.json` → `openapi-typescript openapi.json -o src/api/schema.d.ts`. `openapi.json` не коммитится (артефакт), `schema.d.ts` коммитится — CI перегенерирует и сравнивает. `openapi-fetch` даёт `client.GET('/api/health')` с типами без кодогенерации методов.

## Verification

**Commands:**
- `cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest` -- expected: всё зелёное
- `cd webapp && npm run gen:api && git diff --exit-code src/api/schema.d.ts && npm run lint && npm run build` -- expected: без изменений и ошибок
- `docker compose -f infra/compose.dev.yaml up -d && cd backend && uv run alembic upgrade head` -- expected: миграции применяются из нового пути
