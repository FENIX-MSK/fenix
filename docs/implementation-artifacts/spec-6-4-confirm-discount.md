---
title: 'Story 6.4: Подтверждение скидки при выдаче'
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

**Problem:** Скидку должны получать только те, кому она положена.

**Approach:** При «Выдан» / «Доставлен» с заявкой сначала лист «Подтвердить скидку / Снять — без скидки N ₽». `POST /api/v1/staff/orders/{id}/discount`: подтверждение оставляет сумму, снятие возвращает цены позиций и сумму без скидки; запись в журнале с сотрудником, версия растёт. Выдать без решения нельзя (`discount_decision_required`).

## Boundaries & Constraints

**Always:** решение одно (`no_discount_claim` повторно); устаревшая версия — 409.

**Never:** смены статуса заказа этим действием.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Подтвердить | `pending` | `confirmed`, сумма со скидкой, журнал | — |
| Снять | `pending` | `rejected`, полная сумма в позициях и заказе | — |
| Выдать без решения | — | — | 422 `discount_decision_required` |
| Повторно | решено | — | 422 `no_discount_claim` |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `ordering/orders.py` -- `decide_discount`, запрет выдачи
- [x] `http/staff_orders.py`
- [x] `Board.tsx`, `OrderSheet.tsx`
- [x] тесты

## Implementation Notes

- Агент принял решения сам.


## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | blind | Оплату на кассе могли отметить до решения по скидке | medium | Сумма платежа разошлась бы с итогом | defer: интерфейс просит решение раньше оплаты; серверная проверка — в отчётах эпика 7 |
