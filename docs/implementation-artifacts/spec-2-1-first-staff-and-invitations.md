---
title: 'Story 2.1: Первый сотрудник и приглашение по ссылке'
type: 'feature'
created: '2026-10-17'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/planning-artifacts/architecture/architecture-fenix-2026-10-16/ARCHITECTURE-SPINE.md'
  - '{project-root}/docs/planning-artifacts/ux-designs/ux-fenix-2026-10-16/EXPERIENCE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** В системе нет сотрудников: некому редактировать меню и принимать заказы, а раздел персонала не защищён.

**Approach:** Модуль `identity` хранит членство пользователя в точке и одноразовые приглашения. Первый сотрудник появляется по username из `.env` сервера (или серверной командой), остальные — по ссылке-приглашению в бот на 24 часа. Все роуты `/api/v1/staff/*` проверяют членство на сервере, а Mini App показывает вход «Персонал» только сотрудникам (FR-19, FR-34, AD-7).

**Decisions (пользователь, 2026-10-17):** решения по истории агент принимает сам, аналитика согласована.

## Boundaries & Constraints

**Always:** сотрудник = активное членство пользователя в точке, ролей нет; токен приглашения хранится только хэшем (SHA-256), в ссылке — `t.me/<bot>?start=inv_<token>`; приглашение одноразовое, срок 24 ч; bootstrap срабатывает только если в точке нет ни одного сотрудника (активного или отключённого); username сравнивается без учёта регистра и `@`; проверка прав — только на сервере.

**Never:** роли внутри персонала; хранение токена в открытом виде; запись метки `inv_…` как источника гостя.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Bootstrap по username | сотрудников нет, `BOOTSTRAP_STAFF_TELEGRAM_USERNAME=Owner`, `/start` от `@owner` | членство создано, бот: «Готово, у вас есть доступ к разделу персонала» | — |
| Bootstrap не повторяется | сотрудник уже есть | обычное приветствие, членства нет | — |
| Команда bootstrap | `fenix-staff bootstrap --telegram-id 42` при пустом штате | пользователь 42 — сотрудник | при непустом штате — отказ с кодом выхода 1 |
| Создание приглашения | сотрудник `POST /api/v1/staff/invitations` | `{url, expires_at}` | — |
| Переход по приглашению | `/start inv_<token>` действующей ссылки | членство создано, ссылка погашена, подтверждение | — |
| Повторный/чужой/просроченный токен | погашенная, неизвестная или старше 24 ч | «Приглашение недействительно — попросите коллегу прислать новое» | — |
| Уже сотрудник | действующая ссылка у сотрудника | подтверждение, ссылка не гасится | — |
| Гость в API персонала | `GET /api/v1/staff/me` не сотрудником | 403 `forbidden` | единый формат |
| Признак в Mini App | `GET /api/v1/me` | `is_staff: true/false`; кнопка «Персонал» только сотруднику | — |

</frozen-after-approval>

## Code Map

- `backend/src/fenix/modules/identity/{models,service,api}.py` -- пользователь; добавить членство и приглашения
- `backend/src/fenix/modules/locations/api.py` -- `get_default_location_id` для точки сотрудника
- `backend/src/fenix/http/{auth,router,me}.py` -- `current_user`; добавить `current_staff` и `/staff` роутер
- `backend/src/fenix/telegram/handlers/start.py` -- обработка `/start`; разбор `inv_` и bootstrap
- `backend/src/fenix/platform/config.py` -- `bootstrap_staff_telegram_username`, `telegram_bot_username`
- `.github/workflows/deploy.yml` -- переменная окружения → `.env`
- `webapp/src/{App.tsx,guest/Header.tsx}` -- кнопка «Персонал»; новый `src/staff/` (ленивая загрузка)

## Tasks & Acceptance

**Execution:**
- [x] `identity/models.py` + миграция -- `identity_staff_memberships` (user, location, is_active, created_at, disabled_at, unique user+location), `identity_invitations` (token_hash unique, location, created_by, expires_at, used_at, used_by)
- [x] `identity/{staff,api}.py` -- `is_staff`, `bootstrap_first_staff`, `create_invitation`, `accept_invitation` (атомарно: `UPDATE … WHERE used_at IS NULL AND expires_at > now()`), DTO `StaffMember`
- [x] `http/{auth,staff}.py` -- `current_staff` (403 `forbidden`), `/api/v1/staff/me`, `POST /api/v1/staff/invitations`; `/api/v1/me` → `is_staff`
- [x] `telegram/handlers/start.py` -- `inv_` приглашения, bootstrap по username, тексты EXPERIENCE.md
- [x] `fenix/staff_cli.py` + `fenix-staff bootstrap --telegram-id` -- резервный путь
- [x] `deploy.yml` -- `BOOTSTRAP_STAFF_TELEGRAM_USERNAME` из переменных окружения
- [x] `webapp/src/staff/{StaffApp,InviteScreen}.tsx` + кнопка в шапке -- раздел персонала с нижней навигацией (Заказы · Стоп-лист · Меню · Ещё), экран приглашения: «Пригласить» → ссылка, «Отправить в Telegram» (share URL), «Скопировать»
- [x] тесты матрицы

**Acceptance Criteria:**
- Given стенд, when `fenix-smoke`, then неподписанный и не-сотрудник получают 401/403 на `/api/v1/staff/me`

## Implementation Notes

- Спека написана и утверждена агентом (пользователь делегировал решения 2026-10-17).
- Членство и приглашения — в `identity` (AD-2); у таблиц FK на `locations_locations` без импорта моделей другого модуля. Bootstrap сериализуется `pg_advisory_xact_lock` по точке; закрывается навсегда, как только у точки был хоть один сотрудник (в т.ч. отключённый).
- Погашение приглашения — условный `UPDATE … WHERE used_at IS NULL RETURNING`: из двух одновременных переходов выигрывает один. Отключённый сотрудник по новой ссылке включается обратно (та же строка членства).
- Username бота для ссылок — `TELEGRAM_BOT_USERNAME` или `getMe` (кешируется в процессе API); недоступный Telegram → 503 `telegram_unavailable`.
- `BOOTSTRAP_STAFF_TELEGRAM_USERNAME` попадает на сервер из переменной окружения GitHub `production` через deploy-workflow.
- Mini App: `/api/v1/me` → `is_staff`; кнопка «Персонал» в шапке только сотрудникам; раздел `src/staff/` — отдельный чанк (React.lazy), нижняя навигация Заказы · Стоп-лист · Меню · Ещё; «Ещё → Сотрудники → Пригласить»: ссылка, «Отправить в Telegram» (`t.me/share`), «Скопировать».
- Смоук стенда проверяет 403 на `/api/v1/staff/me` для не-сотрудника.

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge-case | Два одновременных `/start` от владельца могли дважды пройти проверку «нет сотрудников» | low | Проверка и вставка в разных выражениях | patch: advisory-lock на точку |
| 2 | edge-case | Сотрудник, открывший свою же ссылку, «сжигал» её | low | Ссылка предназначена коллеге | patch: у действующего сотрудника ссылка не гасится, тест |
| 3 | blind | Метка `inv_…` попадала бы в источник гостя | medium | `source` брался из payload | patch: источник `staff_invite`, тест |
| 4 | edge-case | Пользователь с тем же username после появления штата | false | Bootstrap закрыт навсегда, тест | reject |

## Verification

**Commands:**
- `cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest && uv run alembic check` -- expected: зелёное
- `cd webapp && npm run gen:api && git diff --exit-code src/api/schema.d.ts && npm run lint && npm run build` -- expected: без ошибок
