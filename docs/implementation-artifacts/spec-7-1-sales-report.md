---
title: 'Story 7.1: Отчёт по продажам'
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

**Problem:** Владелец хочет понимать, как работает кафе и бот.

**Approach:** Модуль `reporting` собирает отчёт через API `ordering`, `payments`, `identity` (AD-2): выручка по выданным и доставленным, число заказов, средний чек, разбивки по способу оплаты (фактическому) и получения, топ-10 блюд, отмены по причинам, новые гости по источникам. Период — сегодня / неделя / месяц / произвольный, границы — местные полуночи точки (AD-11). Экран «Ещё → Отчёты».

## Boundaries & Constraints

**Always:** смоук-пользователь (Telegram id 1) исключён; неоплаченные онлайн-заказы не считаются; произвольный период — не больше года.

**Never:** прямых запросов `reporting` к чужим таблицам.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Сегодня | 2 выданных, 1 отмена | выручка = сумма выданных, средний чек, «Нет продуктов: 1» | — |
| Период наоборот | конец < начала | — | 422 `bad_period` |
| Гость | — | — | 403 |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `reporting/{sales,api}.py`, `ordering.orders_between`, `identity.new_users_by_source`
- [x] `http/staff_reports.py`
- [x] `webapp/src/staff/ReportsScreen.tsx`
- [x] тесты `test_reports.py`

## Implementation Notes

- Агент принял решения сам.


## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | Тестовый гость с id 42 попадал в «технические» | medium | Диапазон id был широким | patch: исключается только смоук-пользователь |
