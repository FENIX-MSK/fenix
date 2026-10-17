---
title: 'Story 5.3: Доставка: передача курьеру и вручение'
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

**Problem:** Гость должен знать, что заказ в пути, а сотрудник — вести доставку до двери.

**Approach:** Для доставки следующий шаг после «Готов» — «Передан курьеру» (`dispatch`), затем «Доставлен» (`deliver`; при оплате на месте — выбор «Наличными / Картой»). Колонка «В доставке» показывает адрес, телефон и «сдачу с». Гость получает «уже едет к вам» и «доставлен».

## Boundaries & Constraints

**Always:** для самовывоза `dispatch` недоступен, для доставки недоступен `hand_over` (таблица AD-3); проверка допустимости до отметки оплаты.

**Never:** трекинга курьера.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Доставка | ready → dispatch → deliver | `delivering` → `delivered`, сообщения гостю | без оплаты — 422 `payment_required` |
| Самовывоз | dispatch | — | 422 `transition_not_allowed` |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `http/staff_orders.py` -- `is_allowed`, оплата при вручении
- [x] `notifications/messages.py`
- [x] `webapp/src/staff/orders/*` -- колонка «В доставке»
- [x] тесты

## Implementation Notes

- Агент принял решения сам.


## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | «Выдан» неоплаченной доставки требовал оплату раньше, чем проверялся переход | low | Вводило в заблуждение | patch: сначала таблица переходов |
