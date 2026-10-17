---
title: 'Story 3.8: Ведение заказа по статусам и оплата на месте'
type: 'feature'
created: '2026-10-17'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/planning-artifacts/architecture/architecture-fenix-2026-10-16/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Сотрудник ведёт заказ до выдачи и отмечает оплату на кассе, гость видит статусы.

**Approach:** Одна главная кнопка следующего шага на карточке: «Принять» (лист со временем готовности: по умолчанию сейчас + время приготовления, пресеты 10–60 мин) → «Готовится» → «Готов» → «Выдан». `POST /api/v1/staff/orders/{id}/actions` с `expected_version`; выдача неоплаченного заказа на месте требует указать «Наличными / Картой» (`payment_required` иначе) — фиксируются способ, сотрудник и время. Отдельно — «Оплачено наличными / картой» в карточке.

## Boundaries & Constraints

**Always:** только переходы из таблицы AD-3; устаревшая версия → 409 `order_conflict`, клиент показывает «Заказ уже изменили» и перечитывает; журнал с именами сотрудников в карточке.

**Never:** выдачи без отметки оплаты для оплаты на месте.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Принять | `new`, время по умолчанию | `accepted`, `ready_at` = сейчас + 20 мин, гостю «принят, будет готов к …» | — |
| Своё время | `ready_at` указан | сохраняется | — |
| Одновременно | два сотрудника | второй — 409 `order_conflict` | — |
| Выдать неоплаченный | `ready`, на месте | без `paid_with` → 422 `payment_required`; с ним — платёж `paid` + `handed_over` | — |
| Повторная отметка | уже оплачен | — | 409 `already_paid` |
| Журнал | после выдачи | create, accept, start_cooking, mark_ready, hand_over с именами | — |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `http/staff_orders.py` -- действия, оплата на месте
- [x] `payments.record_on_site`
- [x] `webapp/src/staff/orders/{Board,OrderCard,OrderSheet}.tsx`
- [x] тесты `test_order_flow.py`

## Implementation Notes

- Агент принял решения сам.
- Проверено в браузере локально: Принять → Готовится → Готов → Выдан.

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | blind | Платёж на месте записан, а переход упал (конфликт) | medium | Деньги отмечены без выдачи | patch: одна транзакция запроса — откатывается всё |
