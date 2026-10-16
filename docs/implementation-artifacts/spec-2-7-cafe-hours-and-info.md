---
title: 'Story 2.7: Часы работы и информация о кафе'
type: 'feature'
created: '2026-10-17'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/implementation-artifacts/spec-1-3-location-hours-and-info.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Адрес и телефон — заглушки, часы работы заданы наполнением; поменять их может только программист.

**Approach:** «Ещё → Кафе» в разделе персонала: часы по дням недели, адрес с координатами для карты, телефон, соцсети, описание и фото кафе; гости видят изменения в «О кафе» и в статусе сразу после сохранения (FR-30, FR-33).

## Boundaries & Constraints

**Always:** закрытие раньше или равно открытию — работа после полуночи (равно — круглосуточно), невыбранный день — выходной; время `H:MM`/`HH:MM`; адрес и телефон обязательны; координаты обе или никаких; ссылки соцсетей только `https://`; до 10 фото, фото обрабатываются как фото блюд (общий `platform/images`).

**Never:** смена часового пояса из интерфейса; несколько интервалов в один день.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Контакты | новый адрес, координаты, телефон | «О кафе» и ссылка карты по координатам | — |
| После полуночи | 18:00–2:00, без воскресенья | часы сохранены, воскресенье — выходной | — |
| Круглосуточно / без часов | 0:00–0:00 все дни / пусто | «Открыто круглосуточно» / «Закрыто» сразу | — |
| Неверное время | 25:00 | 422 `bad_time` | форма сохраняется |
| Повтор дня | два понедельника | 422 `bad_weekday` | — |
| Пустой телефон | «  » | 422 `contacts_required` | — |
| Одна координата | широта без долготы | 422 `bad_coordinates` | — |
| Опасная ссылка | `javascript:` | 422 `bad_social_link` | — |
| Фото кафе | PNG → | `/media/cafe/<id>/<uuid7>.webp` у гостей; удаление убирает | `unsupported_image`, `too_many_photos` |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `platform/images.py` -- обработка фото вынесена из `catalog` (нужна и `locations`, а `locations → catalog` запрещено AD-1)
- [x] `locations/{models,editor,api}.py` + миграция 0005 (`photo_keys`) -- обновление точки и часов, фото
- [x] `http/staff_location.py`, `http/location.py` -- `PUT /staff/location`, `POST/DELETE /staff/location/photos`, `photos` у гостей
- [x] `webapp/src/staff/{CafeScreen,photoUpload}.tsx`, `guest/AboutScreen.tsx` -- форма кафе и лента фото
- [x] тесты матрицы

## Implementation Notes

- Агент принял решения сам (поручение пользователя 2026-10-17). Часы заменяются целиком по присланному списку дней; строки существующих дней обновляются.
- JSONB-поле фото переприсваивается новым списком — изменения на месте SQLAlchemy не замечает.
- Координаты в форме восстанавливаются из `map_url`; время в `<input type=time>` дополняется ведущим нулём.

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | blind | Ссылка `javascript:` в соцсетях открылась бы из «О кафе» | high | Гость нажимает кнопку со ссылкой из БД | patch: только `https://`, тест |
| 2 | edge-case | `append` в JSONB-список не сохранялся бы | medium | SQLAlchemy не отслеживает мутации JSONB | patch: новый список при каждом изменении |
