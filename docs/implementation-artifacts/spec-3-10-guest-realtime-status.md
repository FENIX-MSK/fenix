---
title: 'Story 3.10: Статус заказа у гостя в реальном времени'
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

**Problem:** Гость не должен писать в кафе «ну что там» — экран заказа обновляется сам.

**Approach:** Экран заказа подписывается на канал `order:<order_id>` того же WebSocket и перечитывает заказ по сигналу; страховочный опрос раз в 30 с. Кнопки в сообщениях бота открывают Mini App сразу на экране заказа (`?order=<id>`).

## Boundaries & Constraints

**Always:** подписка на чужой заказ — 4403; экран не мигает при обновлении (данные остаются до ответа).

**Never:** состояния в сигнале.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Смена статуса | сотрудник принял | экран обновился ≤ 5 с | — |
| Оплата прошла | тестовая оплата | «Ждём оплату» → «Отправлен в кафе» без перезагрузки | — |
| Чужой заказ | другой гость | — | WS 4403, REST 404 |
| Ссылка из бота | `?order=<id>` | экран заказа | — |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `webapp/src/api/signals.ts`, `OrderScreen.tsx`, `App.tsx` (диплинк)
- [x] тесты `test_ws.py`

## Implementation Notes

- Агент принял решения сам.
- Проверено в браузере локально и смоуком на стенде (`order-realtime`).

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | После переподключения сигналы за время обрыва потеряны | low | Сигналы не хранятся | patch: `reconnected` → перечитывание |
