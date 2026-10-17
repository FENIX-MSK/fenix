---
title: 'Story 3.5: Тестовая онлайн-оплата и автоотмена'
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

**Problem:** Гость хочет оплатить онлайн; до v1 эквайринга нет, но путь оплаты и автоотмена неоплаченных должны работать.

**Approach:** Модуль `payments` владеет платежами (AD-9): попытка на заказ с ключом (order_id, attempt), провайдер за интерфейсом, сейчас `MockProvider`. В Mini App — экран оплаты в тестовом режиме: «Оплатить» / «Отказ банка (тест)», что приходит в `payments` как уведомление провайдера. Успех → `payments.payment.succeeded` → подписчик `ordering` переводит заказ в `new`. Воркер раз в 30 с отменяет `pending_payment` старше таймаута точки (15 мин).

## Boundaries & Constraints

**Always:** повторное уведомление и повторное событие — без второго перехода; новая попытка закрывает предыдущую; оплата закрытой (отменённой) попытки отклоняется (`payment_cancelled`); статус оплаты заказа — проекция платежей; таймер «осталось N мин» на экране оплаты.

**Never:** реального эквайринга и фискализации (после v1); записи статуса оплаты из `ordering`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Онлайн-заказ | «Онлайн» | `pending_payment`, платёж `pending`, `pay_until` = создан + 15 мин | — |
| Успех | «Оплатить» | платёж `paid`, заказ → `new` ровно один раз, гостю «Оплата прошла…» | — |
| Повтор уведомления | второй успех | без изменений | — |
| Отказ | «Отказ банка» | `failed`, кнопка «Повторить» | — |
| Повторить | после отказа | новая попытка `pending` | `already_paid` 409 |
| Просрочен | > 15 мин без оплаты | попытка `cancelled`, заказ `cancelled`, гостю «оплата не поступила вовремя» | поздняя оплата → 409 `payment_cancelled` |
| Чужой платёж | другой гость | — | 404 |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `payments/{models,provider,service,api}.py` -- платежи, `MockProvider`, проекция статуса
- [x] `ordering/api.py` -- подписчик `payments.payment.succeeded`, `overdue_unpaid`, `cancel_unpaid`
- [x] `worker.py` -- `cancel_overdue_unpaid` раз в 30 с
- [x] `http/orders.py` -- `POST /orders/{id}/payments`, `POST /payments/{id}/test-result`, `pay_until`
- [x] `webapp/src/guest/OrderScreen.tsx` -- экран тестовой оплаты
- [x] тесты в `test_order_flow.py`

## Implementation Notes

- Агент принял решения сам.
- Проверено в браузере локально: онлайн-заказ → «Оплатить» → экран сам перешёл в «Отправлен в кафе» (WebSocket).

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | Автоотмена и оплата в одну секунду | medium | Оплата отменённой попытки дала бы деньги без заказа | patch: воркер сначала закрывает попытку, `handle_notification` отклоняет закрытую |
| 2 | blind | Реальный провайдер может списать деньги по закрытой попытке | low | Только для реального эквайринга | defer: при подключении провайдера — возврат по такому уведомлению |
