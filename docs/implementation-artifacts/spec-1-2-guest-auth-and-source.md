---
title: 'Story 1.2: Гость авторизуется в Mini App и запоминается с источником'
type: 'feature'
created: '2026-10-16'
status: 'done'
baseline_commit: '7dadf4bb89509f9a6446811bf7599a4323d6dbec'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Сервер не знает гостя: нет пользователей, запросы Mini App не аутентифицируются, метка источника из QR-ссылки теряется.

**Approach:** Модуль `identity` хранит пользователя как пару `(platform, external_id)` с меткой источника первого запуска; бот создаёт пользователя на `/start`, а каждый запрос `/api/v1` проверяет подпись `initData` и выполняется от имени пользователя (FR-1, AD-7, NFR-5).

## Boundaries & Constraints

**Always:** проверка подписи по алгоритму Telegram (HMAC-SHA256, ключ — HMAC("WebAppData", токен бота)), `auth_date` не старше 24 ч и не из будущего; сравнение хэша за постоянное время; метка источника пишется только при создании пользователя; таблица `identity_users`, id — UUIDv7; в логи не попадают имя, username и `initData`.

**Never:** обход проверки подписи (в т.ч. в local); хранение телефона и других ПДн сверх имени и username из Telegram; Telegram-специфика в модуле `identity` (парсинг `initData` — в `platform`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Старт без метки | `/start` нового гостя | пользователь `(telegram, id)` с источником `direct`, приветствие и кнопка «Открыть меню» | — |
| Старт с меткой | `/start qr_table` нового гостя | источник `qr_table` | — |
| Повторный старт | `/start promo` у существующего | источник не меняется | — |
| Некорректная метка | `/start` с символами вне `[A-Za-z0-9_-]` или длиннее 64 | источник `direct` | — |
| Верный initData | `Authorization: tma <initData>`, подпись верна, возраст < 24 ч | роут v1 выполняется от имени пользователя; новый создаётся (источник — `start_param` или `direct`) | — |
| Нет/чужая схема заголовка | без заголовка или `Bearer …` | 401 `unauthorized` | единый формат |
| Неверная подпись | изменён любой параметр | 401 `unauthorized` | единый формат |
| Устаревший / из будущего | `auth_date` старше 24 ч или > now + 60 с | 401 `unauthorized` | единый формат |
| Повреждённый initData | нет `hash`, `user` не JSON | 401 `unauthorized` | единый формат |

</frozen-after-approval>

## Code Map

- `backend/src/fenix/platform/db.py` -- `Base`, naming convention, фабрики; переиспользовать
- `backend/src/fenix/platform/errors.py` -- `ApiError` для 401 `unauthorized`
- `backend/src/fenix/http/router.py` -- `api_v1`; сюда подключить роутер `me`
- `backend/src/fenix/main.py` -- lifespan кладёт `session_factory` в `app.state`
- `backend/src/fenix/telegram/{bot,polling}.py`, `handlers/start.py` -- диспетчер получает `settings`; добавить `session_factory`
- `backend/migrations/env.py` -- импортировать модели модулей для autogenerate
- `.github/workflows/ci.yml` -- в backend-джобе нет Postgres; тесты с БД его требуют
- `webapp/src/platform/telegram.ts` -- уже отдаёт `initData`; фронт не меняется

## Tasks & Acceptance

**Execution:**
- [x] `backend/src/fenix/platform/messenger_auth.py` -- разбор и проверка Telegram `initData` → `{external_id, first_name, last_name, username, start_param}`; исключение при любом дефекте -- AD-7 в платформе
- [x] `backend/src/fenix/modules/identity/{models,service,api}.py` -- `IdentityUser`; `ensure_user(session, platform, external_id, profile, source)` через `INSERT … ON CONFLICT`: обновляет имя/username, источник не трогает; DTO `User` -- владение AD-2
- [x] `backend/migrations/versions/0001_identity_users.py` -- таблица с `uq (platform, external_id)`, `created_at`/`updated_at` timestamptz -- схема
- [x] `backend/src/fenix/http/{deps,auth,me}.py` -- сессия на запрос (commit/rollback); зависимость `current_user`, подключённая ко всему `api_v1`; `GET /api/v1/me` -- аутентификация каждого запроса
- [x] `backend/src/fenix/telegram/{bot,polling}.py`, `handlers/start.py` -- `/start [метка]` → `ensure_user` с нормализованной меткой; сессия в данных диспетчера -- FR-1
- [x] `backend/tests/conftest.py` + `tests/test_messenger_auth.py`, `test_identity.py`, `test_auth_api.py`, `test_start.py` -- тестовая БД (`TEST_DATABASE_URL`, миграции один раз за сессию, очистка таблиц), подписанный `initData` в тестах; вся матрица
- [x] `.github/workflows/ci.yml` -- сервис `postgres:17` в backend-джобе и `alembic check` -- миграции совпадают с моделями
- [x] `webapp/src/api/schema.d.ts` -- перегенерировать (`/api/v1/me`)

**Acceptance Criteria:**
- Given стенд после миграций, when гость нажимает «Старт», then в `identity_users` одна строка, повторный старт её не дублирует
- Given открытый из Telegram Mini App, when он запрашивает `/api/v1/me`, then ответ — данные этого гостя

## Implementation Notes

- Спека утверждена агентом по поручению пользователя («делай целиком все 1.*»); ~1700 токенов, оставлена целиком, как и 1.1.
- `ensure_user` в обычном случае — один SELECT; запись только при создании пользователя или смене имени/username (запрос идёт на каждый вызов `/api/v1`, NFR-1). Гонка двух первых запросов закрыта `ON CONFLICT DO NOTHING` + повторным SELECT.
- `current_user` подключён как зависимость всего `api_v1`; FastAPI кеширует его в пределах запроса, поэтому `user: CurrentUser` в роуте не проверяет подпись второй раз. Неизвестные пути `/api/v1/*` остаются 404 (зависимости роутера срабатывают только на найденных роутах).
- Сессия на запрос — `Depends(get_session, scope="function")`: транзакция закрывается до отправки ответа, поэтому сбой commit даёт 500, а не 200.
- Naming convention для `uq`/`ix` расширена на все колонки (`column_0_N_name`) до первой миграции: `uq_identity_users_platform_external_id`.
- Тесты с БД используют `fenix_test` (`TEST_DATABASE_URL`), миграции применяются один раз за прогон, таблицы очищаются перед каждым тестом; `TELEGRAM_BOT_TOKEN` в тестах принудительно тестовый — им подписывается `initData`. В CI backend-джоб получил сервис Postgres и шаг `alembic check`.
- В `fenix/platform/db.py` изменилась только naming convention; `ensure_user` возвращает DTO `identity.api.User`, ORM-модель наружу не выходит.

## Spec Change Log

## Review Triage Log

Ревью выполнено inline (субагенты — только по явной просьбе пользователя).

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | blind | UPSERT пользователя на каждый запрос `/api/v1` — запись и commit даже при чтении меню | medium | `ensure_user` выполнял `INSERT … ON CONFLICT DO UPDATE` с `updated_at` при каждом вызове | patch: SELECT, запись только при создании/изменении профиля; тест `test_unchanged_profile_is_not_rewritten` |
| 2 | edge-case | Выход yield-зависимости по умолчанию может выполняться после отправки ответа: сбой commit → 200 без сохранённых данных | low | На пробном приложении FastAPI 0.143 воспроизведено (200); в нашем приложении сейчас 500 — исключение успевает дойти до `ServerErrorMiddleware`, но это держится на составе middleware | patch: `scope="function"`, тест `test_failed_commit_is_not_reported_as_success` фиксирует контракт |
| 3 | edge-case | `user.id = true` проходил бы проверку `isinstance(..., int)` | low | `bool` — подкласс `int` | patch: `type(...) is not int`, кейс `id-not-int` |
| 4 | edge-case | Тесты подписи падали бы в CI: `TELEGRAM_BOT_TOKEN` из окружения CI перекрывал тестовый токен при `setdefault` | medium | В CI задан токен для `alembic`; подписи тестов считаются тестовым токеном | patch: токен в conftest принудительный; прогон с чужим `TELEGRAM_BOT_TOKEN` зелёный |
| 5 | verification-gap | Ветка гонки «два первых запроса одновременно» (`ON CONFLICT DO NOTHING` → повторный SELECT) не покрыта тестом | low | Требует двух параллельных транзакций; код ветки — два выражения | reject: маловероятно в обычной работе, тест потребует отдельной инфраструктуры параллельных сессий |
| 6 | blind | `bind_contextvars(user_id=…)` без очистки | false | Каждый запрос выполняется в своей задаче asyncio с копией контекста; привязка не переходит между запросами | reject |

## Design Notes

`ensure_user` — один запрос: `insert(...).on_conflict_do_update(index_elements=[platform, external_id], set_={first_name, last_name, username, updated_at}).returning(...)` — источник из `values` применяется только при вставке. `external_id` хранится строкой (у MAX id может быть не числом). `current_user` вешается как `dependencies` на `api_v1`, поэтому новые роуты защищены по умолчанию; роуту, которому нужен пользователь, достаточно параметра `user: CurrentUser`.

## Verification

**Commands:**
- `docker compose -f infra/compose.dev.yaml up -d postgres` -- expected: Postgres для тестов
- `cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest && uv run alembic upgrade head && uv run alembic check` -- expected: всё зелёное
- `cd webapp && npm run gen:api && git diff --exit-code src/api/schema.d.ts && npm run lint && npm run build` -- expected: без ошибок
