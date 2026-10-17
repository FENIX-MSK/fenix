---
title: 'Story 6.1: Управление акциями'
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

**Problem:** Кафе хочет проводить скидки без программиста.

**Approach:** «Ещё → Акции»: процент, всё меню или категория, даты (локальные даты точки, включительно), тип «автоматическая» / «с проверкой», текст для гостей, вкл./выкл. Таблица `catalog_promotions` с `location_id`; CRUD `/api/v1/staff/promotions`. Наполнение создаёт «В день рождения — скидка 10% на всё меню» (с проверкой, бессрочная).

## Boundaries & Constraints

**Always:** процент 1–100, окончание не раньше начала, текст обязателен; только персонал.

**Never:** акций на отдельные блюда (охват — всё меню или категория).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Создать | 20%, всё меню | сохранена | — |
| Даты наоборот | конец < начала | — | 422 `bad_dates` |
| 0% | — | — | 422 |
| Наполнение | чистая база | «День рождения» 10% с проверкой | идемпотентно |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `catalog/{models,promotions,api}.py` + миграция 0011
- [x] `http/staff_promotions.py`, `seed.py`
- [x] `webapp/src/staff/PromotionsScreen.tsx`
- [x] тесты `test_promotions.py`

## Implementation Notes

- Агент принял решения сам.


## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | Повторное наполнение создало бы вторую «День рождения» | low | Наполнение при каждом деплое | patch: идемпотентно по наличию акции «с проверкой» |
