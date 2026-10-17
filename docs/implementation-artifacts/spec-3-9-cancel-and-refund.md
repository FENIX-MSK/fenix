---
title: 'Story 3.9: Отмена заказа и возврат'
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

**Problem:** Сотрудник отменяет заказ с причиной; гость узнаёт об отмене, причина остаётся в кафе; онлайн-оплата возвращается.

**Approach:** В карточке «Отменить заказ»: причины (Нет продуктов · Не успеваем · Гость попросил · Другое + поле) и подтверждение вторым нажатием. Причина — в журнале и `cancel_reason`, гостю не показывается. Если заказ оплачен онлайн, событие отмены несёт `refunded`, гость получает «…отменён. Деньги за онлайн-оплату вернутся.», а подписчик `payments.refund` делает возврат через провайдера с повторами.

## Boundaries & Constraints

**Always:** без причины — 422 `reason_required`; отмена до выдачи; возврат — только онлайн-платежа.

**Never:** причины в сообщении или API гостя.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Без причины | `cancel` без `note` | — | 422 `reason_required` |
| С причиной | «нет молока» | `cancelled`, причина в карточке персонала | — |
| Гостю | отмена | «К сожалению, заказ #NNN отменён.» | — |
| Оплачен онлайн | отмена | платёж `refunded`, «Деньги за онлайн-оплату вернутся.» | возврат повторяется до успеха |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `payments.refund`, подписчик `ordering.order.cancelled`
- [x] `http/staff_orders.py` -- `refunded` в событии
- [x] `webapp/src/staff/orders/OrderSheet.tsx` -- форма отмены
- [x] тесты `test_order_flow.py`

## Implementation Notes

- Агент принял решения сам.
- Проверено в браузере локально: отмена с причиной, подтверждение вторым нажатием.

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | blind | Наличные при отмене после оплаты на кассе не «возвращаются» системой | low | Деньги отдаёт кассир | defer: отчёт эпика 7 покажет такие случаи |
