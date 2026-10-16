---
title: 'Story 2.4: Редактор групп модификаторов'
type: 'feature'
created: '2026-10-17'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/implementation-artifacts/spec-2-3-menu-editor.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Добавки и обязательный выбор (соус, котлета, сироп) заведены только наполнением; персонал не может их поменять или привязать к новому блюду.

**Approach:** В «Меню» есть вкладка «Модификаторы»: группа с мин./макс. выбором и опциями с доплатой, привязка к блюдам и к целым категориям (FR-26, FR-4).

## Boundaries & Constraints

**Always:** `0 ≤ мин ≤ макс`, `1 ≤ макс ≤ число опций`, хотя бы одна опция, названия опций в группе уникальны, доплата ≥ 0 копеек; опции сопоставляются по `id` (пропавшие удаляются вместе со стоп-листом); привязки задаются целиком (набор блюд и набор категорий); группа, привязанная и к блюду, и к его категории, в карточке гостя одна.

**Never:** вложенные группы; разные цены опции для разных блюд.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Создание | `POST /staff/modifier-groups` «Соус к фри», 0/1, 2 опции | группа создана | — |
| Мин > макс | 2/1 | 422 `choice_bounds` | — |
| Макс > опций | макс 3 при 2 опциях | 422 `choice_bounds` | — |
| Без опций | `modifiers: []` | 422 `group_needs_option` | — |
| Повтор опции | два «Сироп» | 422 `duplicate_option_name` | — |
| Привязка к категории | `PUT /staff/modifier-groups/{id}/links {category_ids:[Кофе]}` | группа в карточке каждого кофе | — |
| Двойная привязка | к «Капучино» и к «Кофе» | в карточке капучино группа один раз | — |
| Цена опции | изменили доплату | `POST /menu/price` считает новую | — |
| Удаление группы | `DELETE` | привязки и стоп-лист опций удалены | — |

</frozen-after-approval>

## Code Map

- `backend/src/fenix/modules/catalog/{models,dish,editor,api}.py` -- группы, `dish_groups` (дедупликация уже есть)
- `backend/src/fenix/http/staff_catalog.py` -- роуты редактора
- `webapp/src/staff/menu/MenuEditor.tsx` -- добавить переключатель «Блюда / Модификаторы»

## Tasks & Acceptance

**Execution:**
- [x] `catalog/modifier_editor.py` + `api.py` -- список с привязками, create/update/delete, `set_links`
- [x] `http/staff_catalog.py` -- `/staff/modifier-groups…`
- [x] `webapp/src/staff/menu/{ModifierGroups,GroupForm}.tsx` -- список групп, форма (мин/макс, опции с «+N ₽», привязки галочками по категориям и блюдам)
- [x] тесты матрицы

**Acceptance Criteria:**
- Given группа привязана к категории в редакторе, when гость открывает блюдо этой категории, then видит группу в карточке

## Implementation Notes

- `catalog/modifier_editor.py`: группа и опции (по `id`, пропавшие удаляются с каскадом стоп-листа); привязки задаются целиком — `PUT …/links {dish_ids, category_ids}`; новая привязка встаёт после уже показанных групп.
- Дедупликация двойной привязки — в `dish_groups` (1.6), закреплена тестом.
- UI: в «Меню» переключатель «Блюда / Модификаторы»; группа: название, мин/макс с подсказкой, опции с доплатой, «Где предлагать» — галочки категорий («все блюда»), а внутри не выбранной категории — отдельных блюд.

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge-case | Новая группа сохраняется двумя запросами (группа, затем привязки): при сбое второго группа остаётся без привязок | low | Сотрудник видит ошибку и может сохранить снова — форма открыта, группа уже есть в списке | reject: потерь данных нет, повтор безопасен |
| 2 | blind | Привязка к несуществующему блюду | low | Без проверки FK вернул бы 500 | patch: 422 `unknown_link`, тест |

## Verification

**Commands:**
- `cd backend && uv run pytest && uv run mypy && uv run lint-imports` -- expected: зелёное
- `cd webapp && npm run gen:api && npm run lint && npm run build` -- expected: без ошибок
