---
title: 'Story 2.3: Редактор категорий, блюд и размеров'
type: 'feature'
created: '2026-10-17'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/implementation-artifacts/spec-1-4-catalog-and-menu-seed.md'
  - '{project-root}/docs/planning-artifacts/ux-designs/ux-fenix-2026-10-16/EXPERIENCE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Меню можно поменять только кодом: персонал не может добавить блюдо, поправить цену или скрыть позицию.

**Approach:** В разделе персонала «Меню» сотрудник создаёт, меняет, скрывает, переупорядочивает и удаляет категории и блюда, редактирует размеры с ценами; изменения сразу видны гостям, а цена — в `catalog.api.price` (FR-26).

## Boundaries & Constraints

**Always:** все роуты — `/api/v1/staff/*` под проверкой сотрудника; цены — целые копейки; у блюда ≥1 размер; если размеров больше одного, у каждого есть название, названия размеров блюда уникальны; изменение размеров — по `id` (существующие обновляются, без `id` создаются, пропавшие удаляются); категория с блюдами не удаляется; порядок — явными списками id; форма при ошибке сохранения сохраняет введённое.

**Never:** группы модификаторов (2.4), фото (2.5), стоп-лист (2.6); автоматический пересчёт цен в существующих заказах.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Новая категория | `POST /staff/categories {name}` | в конце списка, видна гостям | — |
| Скрытие | `PATCH /staff/categories/{id} {is_hidden:true}` | гостевое меню её не отдаёт | — |
| Новое блюдо | `POST /staff/dishes` с 1 размером | в конце категории, видно гостям | — |
| Без размеров | `sizes: []` | 422 `dish_needs_size` | форма сохраняется |
| Безымянные размеры | 2 размера, один без названия | 422 `size_name_required` | — |
| Повтор названий | два размера «400 мл» | 422 `duplicate_size_name` | — |
| Смена цены | `PUT /staff/dishes/{id}` с новой ценой размера | `POST /menu/price` сразу возвращает новую цену | — |
| Удаление размера | размер пропал из списка | удалён (вместе с записью стоп-листа) | — |
| Чужой размер | `id` размера другого блюда | 422 `foreign_size` | — |
| Порядок | `POST /staff/categories/order {ids}` / `POST /staff/dishes/order {category_id, ids}` | порядок как в списке | 422 `bad_order`, если набор id не совпадает |
| Удаление | категория с блюдами / пустая; блюдо | 409 `category_not_empty` / 200; 200 | единый формат |
| Не сотрудник | любой роут редактора | 403 `forbidden` | — |

</frozen-after-approval>

## Code Map

- `backend/src/fenix/modules/catalog/{models,menu,dish,api}.py` -- модели, гостевое меню, карточка
- `backend/src/fenix/http/{staff,menu}.py` -- роутер персонала, модели ответов меню
- `webapp/src/staff/StaffApp.tsx` -- вкладка «Меню» сейчас заглушка

## Tasks & Acceptance

**Execution:**
- [x] `catalog/editor.py` + `api.py` -- `staff_catalog`, `create/update/delete_category`, `create/update/delete_dish`, `reorder_categories`, `reorder_dishes`; `CatalogEditError(code)`
- [x] `http/staff_catalog.py` -- роуты и модели (`StaffCatalogOut`, `DishIn`, `CategoryIn`)
- [x] `webapp/src/staff/menu/{MenuEditor,CategoryForm,DishForm,PriceInput}.tsx` -- список категорий и блюд (метка «скрыто»), ↑/↓, формы, удаление с подтверждением
- [x] тесты матрицы

**Acceptance Criteria:**
- Given сотрудник изменил цену в редакторе, when гость открывает меню, then видит новую цену

## Implementation Notes

- Редактор — `catalog/editor.py`, наружу через `catalog.api` с DTO (`StaffCategory`, `StaffDish`, `StaffSize`); роуты `http/staff_catalog.py` подключены в роутер персонала, поэтому проверка сотрудника на каждом из них.
- Размеры сопоставляются по `id`; пропавшие удаляются (delete-orphan), записи стоп-листа уходят каскадом FK. При переносе блюда в другую категорию оно встаёт в конец.
- Цена в форме вводится в рублях («199» или «199,50») и переводится в копейки только для ввода; расчёт цены — по-прежнему сервер.
- UI «Меню»: категории раскрываются, ↑/↓ для порядка, ✎ — форма категории, тап по блюду — форма блюда (название, категория, состав, вес/объём, размеры с ценами, «скрыть от гостей»), удаление со вторым подтверждением; при ошибке форма сохраняет введённое.

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge-case | Позиция первой категории в пустом каталоге считалась бы с ошибкой (`(last or 0) + 1 if …`) | low | Выражение давало 1 вместо 0 только при `last = 0`, путая порядок | patch: `0 if last is None else last + 1` |
| 2 | blind | Удаление размера, на который ссылаются будущие корзины (эпик 3) | maybe-false | Корзин ещё нет | defer в эпик 3: корзина должна переживать удалённый размер (предупреждение «закончилось») |

## Verification

**Commands:**
- `cd backend && uv run pytest && uv run mypy && uv run lint-imports` -- expected: зелёное
- `cd webapp && npm run gen:api && npm run lint && npm run build` -- expected: без ошибок
