---
title: 'Story 1.3: Точка, часы работы и информация о кафе'
type: 'feature'
created: '2026-10-16'
status: 'done'
baseline_commit: 'a8ade1f9c433e7126a8f568696462ca2bf1d18c0'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/implementation-artifacts/epic-1-context.md'
  - '{project-root}/docs/planning-artifacts/ux-designs/ux-fenix-2026-10-16/DESIGN.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Гость не видит, где кафе, как с ним связаться и открыто ли оно сейчас; в системе нет сущности «Точка», к которой следующие истории привяжут стоп-лист и заказы.

**Approach:** Модуль `locations` хранит точку с часовым поясом, часами работы по дням недели и информацией о кафе; API отдаёт эти данные вместе со статусом «Открыто до… / Закрыто, откроемся…», вычисленным в поясе точки; Mini App показывает статус в шапке и экран «О кафе» (FR-2, AD-10, AD-11).

**Decisions (пользователь, 2026-10-16):** карта — ссылка «Открыть на карте» на Яндекс Карты; адрес и телефон — заглушки, помеченные для замены заказчиком, часы 9:00–22:00 ежедневно; соцсети — из QR печатного меню: Telegram `https://t.me/phoenix_catering`, MAX `https://max.ru/u/f9LHodD0cOLIKz84G4slSSyEx8nsE00IjfVN_kgD5Au-hDoTTbLto4KeIhw`.

## Boundaries & Constraints

**Always:** время в БД — `time` без зоны для часов работы и `timestamptz` для отметок, бизнес-время — в поясе точки (`Europe/Moscow` по умолчанию); закрытие раньше или равно открытию означает работу после полуночи; день без записи — выходной; статус считает сервер, клиент только показывает; начальное наполнение идемпотентно и не перезаписывает изменения персонала (если точка уже есть — ничего не делает).

**Never:** редактирование данных персоналом (история 2.7); фото кафе (после Garage, 2.5); встроенная карта и внешние скрипты карт; вычисление статуса в браузере.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Открыто | 9:00–22:00, сейчас 12:00 | «Открыто до 22:00» | — |
| До открытия | сейчас 7:30 | «Закрыто, откроемся в 9:00» | — |
| После закрытия | сейчас 22:00 ровно | «Закрыто, откроемся завтра в 9:00» | — |
| После полуночи | пт 18:00–02:00, сейчас сб 01:00 | «Открыто до 2:00» | — |
| Выходной | вс без записи, сейчас сб 23:00 | «Закрыто, откроемся в понедельник в 9:00» (вт — «во вторник») | — |
| Круглосуточно | открытие = закрытие | «Открыто круглосуточно» | — |
| Нет часов | ни одной записи | «Закрыто» | — |
| Пояс точки | сервер в UTC, 06:30 UTC = 9:30 МСК | «Открыто до 22:00» | — |
| Повторное наполнение | точка уже есть | изменений нет | — |
| Без авторизации | `GET /api/v1/location` без `initData` | 401 `unauthorized` | единый формат |

</frozen-after-approval>

## Code Map

- `backend/src/fenix/modules/identity/{models,service,api}.py` -- образец модуля: модели, сервис, DTO в `api.py`
- `backend/src/fenix/http/{router,me,auth}.py` -- подключение роутера, `SessionDep`, аутентификация по умолчанию
- `backend/migrations/env.py`, `tests/conftest.py` -- зарегистрировать модели нового модуля
- `backend/.importlinter` -- новый адаптер `fenix.seed` добавить в контракты адаптеров и `platform`
- `infra/compose.prod.yaml` (`migrate`) -- после `alembic upgrade head` запускать наполнение
- `webapp/src/platform/{types,telegram,browser}.ts` -- добавить BackButton, цвета шапки/фона, `openLink`, признак тёмной темы
- `webapp/src/App.tsx`, `index.css` -- сейчас заглушка; заменить оболочкой с экранами

## Tasks & Acceptance

**Execution:**
- [x] `backend/src/fenix/modules/locations/{models,hours,service,seed,api}.py` -- `locations_locations` (имя, пояс, адрес, телефон, координаты, описание, соцсети JSONB), `locations_opening_hours` (weekday 0–6, opens_at, closes_at, unique по точке и дню); чистая функция статуса и русская формулировка; `get_default_location`, `seed_default_location` -- AD-2, AD-11
- [x] `backend/migrations/versions/…_0002_locations.py` -- таблицы -- схема
- [x] `backend/src/fenix/seed.py` + команда `fenix-seed` в `pyproject.toml` -- идемпотентное наполнение всех модулей -- AC начального наполнения
- [x] `infra/compose.prod.yaml` -- `migrate`: `alembic upgrade head && fenix-seed` -- данные на стенде после деплоя
- [x] `backend/src/fenix/http/location.py` -- `GET /api/v1/location`: информация, часы, `status {is_open, text, closes_at, opens_at}` (ISO с зоной), `map_url` Яндекс Карт -- FR-2
- [x] `backend/tests/test_opening_status.py`, `test_location_api.py`, `test_seed.py` -- вся матрица; время подставляется параметром `now`
- [x] `webapp/src/platform/*` -- BackButton, `setColors(bg)`, `openLink`, `isDark`; браузерная реализация — no-op/`window.open`
- [x] `webapp/src/{App.tsx,index.css,theme.css}`, `src/guest/{Header,AboutScreen,useLocation}.tsx` -- токены DESIGN.md как CSS-переменные (светлая/тёмная по теме Telegram), Tenor Sans с кириллицей из пакета `@fontsource/tenor-sans` (без внешних CDN), шапка «ФЕНИКС» со статусом, экран «О кафе» (адрес + «Открыть на карте», часы по дням, телефон `tel:`, соцсети), возврат BackButton -- FR-2, NFR-7
- [x] `webapp/src/api/schema.d.ts` -- перегенерировать

**Acceptance Criteria:**
- Given чистая база, when выполняются `alembic upgrade head` и `fenix-seed`, then существует точка «Феникс бистро» (`Europe/Moscow`) с часами на 7 дней, заглушками адреса/телефона и двумя соцсетями
- Given открытый Mini App, when гость открывает «О кафе» и возвращается BackButton, then виден статус, адрес со ссылкой на карту, часы, телефон и соцсети; экран корректен от 360 px в светлой и тёмной теме

## Implementation Notes

- Спека утверждена агентом по поручению пользователя («делай целиком все 1.*»).
- Наполнение — команда `fenix-seed` (адаптер `fenix/seed.py`, добавлен в контракты import-linter); модуль пропускает наполнение, если точка уже есть, поэтому повторный запуск на каждом деплое не трогает правки персонала. В `infra/compose.prod.yaml` сервис `migrate` выполняет `alembic upgrade head && fenix-seed`.
- Статус возвращается сервером и готовым текстом (`status.text`), и моментами `closes_at`/`opens_at` в поясе точки (ISO с `+03:00`). Последовательные интервалы склеиваются; «Открыто круглосуточно» — когда все 7 дней 0:00–0:00.
- Шрифт Tenor Sans — пакет `@fontsource/tenor-sans` (кириллица + латиница), без внешних CDN. Токены DESIGN.md — CSS-переменные в `src/theme.css`, тёмная тема — `html[data-theme='dark']` по `isThemeParamsDark()`; цвет шапки и фона Telegram = `--bg`.
- `platform` расширен: `isDark`, `setColors`, `showBackButton`, `hasNativeBackButton`, `openLink`. В браузере вне Telegram экран показывает ссылку «← В меню».
- Для проверки вне клиента Telegram в dev подключается `mockTelegramEnv` SDK (`platform/devTelegramMock.ts`), если страница открыта с `#tgWebAppData=…` в обычной вкладке: без этого SDK бросал `UnknownEnvError` и приложение не рендерилось. Сбой `platform.init()` больше не роняет приложение (try/catch в `main.tsx`).
- Проверено в браузере на 360 px: шапка «ФЕНИКС · Открыто до 22:00», экран «О кафе», возврат по событию `back_button_pressed`, светлая и тёмная тема Telegram.

## Spec Change Log

## Review Triage Log

Ревью выполнено inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge-case | Вне клиента Telegram (dev-вкладка с launch-параметрами) `init()` бросает `UnknownEnvError`, приложение пустое | medium | Воспроизведено в браузере | patch: dev-мок `mockTelegramEnv`, try/catch вокруг `platform.init()` |
| 2 | edge-case | Тест «круглосуточный понедельник» ожидал «до 22:00», хотя вторник начинается в 9:00 | low | Ожидание теста было неверным: интервалы не стыкуются, правильно «до 0:00» | patch: исправлен тест, добавлен тест стыкующихся интервалов |
| 3 | blind | Смена темы Telegram во время работы приложения не применяется | low | Тема читается один раз при запуске; событие `theme_changed` не слушается | defer |
| 4 | blind | Статус в шапке не обновляется, если приложение открыто через момент закрытия | low | Данные загружаются один раз | reject: сессия Mini App короткая, при следующем открытии статус верный |
| 5 | edge-case | Некорректный часовой пояс точки дал бы 500 | low | Пояс задаётся наполнением (`Europe/Moscow`); редактирования ещё нет | defer: валидация пояса — в редакторе (2.7) |

## Design Notes

Статус: интервалы вчерашнего и сегодняшнего дня (`[date+opens, date+closes (+1 день, если closes ≤ opens))`) в поясе точки; открыто, если `now` внутри; иначе ближайшее начало интервала в следующие 7 дней. Время — «9:00», «22:00» (часы без ведущего нуля). День: сегодня — без слова, завтра — «завтра», иначе «в понедельник / во вторник / в среду / в четверг / в пятницу / в субботу / в воскресенье». Ссылка карты: `https://yandex.ru/maps/?pt={lon},{lat}&z=17&l=map` при координатах, иначе `https://yandex.ru/maps/?text={адрес}`.

## Verification

**Commands:**
- `cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest && uv run alembic upgrade head && uv run alembic check && uv run fenix-seed && uv run fenix-seed` -- expected: зелёное, повторное наполнение без изменений
- `cd webapp && npm run gen:api && git diff --exit-code src/api/schema.d.ts && npm run lint && npm run build` -- expected: без ошибок
- `cd infra && docker compose -f compose.prod.yaml config -q` (с `.env` из примера, как в CI) -- expected: валидно

**Manual checks:**
- Mini App в браузере с подписанным `initData` (URL `#tgWebAppData=…`): шапка со статусом, «О кафе», возврат; ширина 360 px, светлая и тёмная схема
