---
title: 'Story 1.5: Гость листает меню'
type: 'feature'
created: '2026-10-16'
status: 'done'
baseline_commit: 'bce284353a3af25f87e8ee6d0d306dd781c4dc2d'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/implementation-artifacts/epic-1-context.md'
  - '{project-root}/docs/planning-artifacts/ux-designs/ux-fenix-2026-10-16/DESIGN.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Меню есть в базе, но гость его не видит: главный экран Mini App — заглушка.

**Approach:** API отдаёт меню точки одним запросом — видимые категории и блюда с ценой «от», порцией и признаком «Закончилось» по стоп-листу; главный экран показывает шапку со статусом, прилипающую карусель категорий и карточки блюд (FR-3, NFR-1, NFR-7).

## Boundaries & Constraints

**Always:** скрытые категории и блюда не отдаются; «Закончилось» — когда все размеры блюда в стоп-листе точки; цена «от» — минимальная среди доступных размеров (если закончились все — среди всех), признак «от» — если у блюда больше одного размера; цены считает сервер, клиент только форматирует копейки в «N ₽»; карточка «Закончилось» приглушена, помечена текстом и не нажимается; карусель прилипает и подсвечивает категорию при прокрутке; скелетоны при загрузке; экран от 360 px, светлая и тёмная тема, две колонки карточек от 768 px.

**Never:** лист блюда и выбор модификаторов (1.6); корзина и полоса корзины (эпик 3); баннер акции (эпик 6); индикатор загруженности кухни (5.7); фото из хранилища (2.5) — пока заглушка с лучами.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Меню | наполненный каталог | 10 категорий в порядке PDF, блюда в порядке PDF | — |
| Один размер | Филадельфия | `price_from` 69900, `has_sizes` false → «699 ₽» | — |
| Несколько размеров | Картофель фри | `price_from` 12900, `has_sizes` true → «от 129 ₽» | — |
| Часть размеров в стоп-листе | у капучино закончился 250 мл | `price_from` 25000, `sold_out` false | — |
| Все размеры в стоп-листе | фри М и Б | `sold_out` true, карточка «Закончилось», не открывается | — |
| Стоп-лист другой точки | запись для другой точки | не влияет | — |
| Скрытое | скрытая категория / скрытое блюдо | не отдаются | — |
| Пустая категория | все блюда категории скрыты | категория отдаётся без блюд, экран — «Здесь пока пусто» | — |
| Нет связи | запрос меню не удался | «Не получилось связаться с кафе…» и «Попробовать ещё раз» | повтор |

</frozen-after-approval>

## Code Map

- `backend/src/fenix/modules/catalog/{models,api}.py` -- модели из 1.4; добавить чтение меню
- `backend/src/fenix/modules/locations/api.py` -- `get_default_location` даёт `location_id` для стоп-листа
- `backend/src/fenix/http/{router,location}.py` -- образец роутера и pydantic-моделей ответа
- `webapp/src/App.tsx` -- заменить заглушку меню; `guest/Header.tsx`, `useLocationInfo.ts`, `theme.css`, `index.css` -- переиспользовать
- `webapp/src/guest/SunMark.tsx` -- лучи для заглушки фото

## Tasks & Acceptance

**Execution:**
- [x] `backend/src/fenix/modules/catalog/{menu,api}.py` -- `get_menu(session, location_id)`: категории → блюда → размеры + стоп-лист точки за фиксированное число запросов; DTO `MenuCategory`, `MenuDish` -- FR-3
- [x] `backend/src/fenix/http/menu.py` -- `GET /api/v1/menu` -- точка подключения Mini App
- [x] `backend/tests/test_menu_api.py` -- вся матрица (кроме «Нет связи») -- регрессия
- [x] `webapp/src/guest/{MenuScreen,CategoryCarousel,DishCard,useMenu,format}.ts(x)` + стили -- главный экран по DESIGN.md; карточки — кнопки с `onOpen` (лист — 1.6) -- FR-3
- [x] `webapp/src/App.tsx` -- меню вместо заглушки -- главный экран
- [x] `webapp/src/api/schema.d.ts` -- перегенерировать

**Acceptance Criteria:**
- Given наполненная база, when 200 запросов `/api/v1/menu` подряд локально, then p95 ≤ 300 мс (NFR-1)
- Given Mini App на 360 px, when гость листает меню, then карусель прилипает и переключает активную категорию, «Закончилось» видно текстом, светлая и тёмная тема корректны

## Implementation Notes

- Спека утверждена агентом по поручению пользователя.
- `catalog.api.get_menu` — 3 запроса (категории → блюда → размеры, `selectinload`) плюс стоп-лист точки; адаптер берёт `location_id` из `locations.api.get_default_location_id`. Замер локально: 200 запросов `/api/v1/menu` (≈20 КБ) — p50 23 мс, p95 24 мс.
- Фронтенд: общий хук `useRemote` (загрузка/ошибка/повтор) для точки и меню; карусель — sticky, активная категория — IntersectionObserver по полосе под каруселью с полным набором пересекающих секций, у дна страницы — последняя категория.
- Проверено в браузере: 360 px и 800 px (две колонки), светлая и тёмная тема, «Закончилось» у картофеля фри при обоих размерах в стоп-листе, переход по чипсу, подсветка при прокрутке до «Десертов».
- Фото пока нет: заглушка с лучами; `photo_url` в API всегда `null` до истории 2.5.

## Spec Change Log

## Review Triage Log

Ревью выполнено inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge-case | Scroll-spy выбирал среди изменившихся записей IntersectionObserver, а не среди всех пересекающих: после ресайза активный чипс отставал | medium | Воспроизведено на 800 px: на экране «Напитки», активен «Лепёшки» | patch: множество пересекающих секций |
| 2 | edge-case | Короткие последние секции не доходят до полосы — «Десерты» никогда не активны | medium | Воспроизведено | patch: у дна страницы активна последняя категория |
| 3 | blind | Зона нажатия чипса 36 px < 44 px (Accessibility Floor) | medium | Комментарий в CSS ошибочно считал отступ списка частью кнопки | patch: `min-height: var(--tap-min)` |
| 4 | blind | Предупреждения oxlint (`exhaustive-deps`, `set-state-in-effect`) | low | Линтер | patch |
| 5 | verification-gap | Нет автотестов фронтенда (scroll-spy, «Закончилось») | low | В webapp нет тестового раннера | defer: тестовый раннер Mini App — отдельной задачей |

## Design Notes

Ответ: `{categories: [{id, name, description, dishes: [{id, name, description, portion, price_from, has_sizes, sold_out, photo_url}]}]}`; `portion` — порция блюда или первого размера. Цена в UI: `Math.round(kopecks / 100)` с неразрывным пробелом и «₽»; копейки в меню всегда целые рубли. Прокрутка: `IntersectionObserver` по секциям категорий; нажатие на чипс прокручивает к секции с учётом высоты прилипшей карусели.

## Verification

**Commands:**
- `cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest` -- expected: зелёное
- `cd webapp && npm run gen:api && git diff --exit-code src/api/schema.d.ts && npm run lint && npm run build` -- expected: без ошибок

**Manual checks:**
- Mini App с подписанным `initData` на 360 и 800 px, светлая и тёмная тема; блюдо в стоп-листе — «Закончилось»
