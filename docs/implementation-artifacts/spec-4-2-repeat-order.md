---
title: 'Story 4.2: Повтор заказа'
type: 'feature'
created: '2026-10-17'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/planning-artifacts/ux-designs/ux-fenix-2026-10-16/EXPERIENCE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Любимый заказ хочется оформить за секунды.

**Approach:** «Повторить» в «Моих заказах»: `POST /api/v1/orders/{id}/repeat` кладёт позиции заказа в корзину с теми же размерами, модификаторами и количеством через обычное добавление в корзину (та же проверка доступности); цены — текущие (AD-6). Недоступные позиции пропускаются и называются над корзиной: «Сырники закончились — мы не добавили это в корзину».

## Boundaries & Constraints

**Always:** чужой заказ — 404; каждая позиция добавляется в своей точке сохранения, сбой одной не ломает остальные.

**Never:** цен из старого заказа.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Всё доступно | 2 позиции | обе в корзине, итог по текущим ценам | — |
| Стоп-лист | одна в стоп-листе | `added: 1`, `skipped: ["Филадельфия"]`, сообщение над корзиной | — |
| Ничего нет | все недоступны | остаёмся в «Моих заказах»: «Ничего из этого заказа сейчас нет в меню.» | — |
| Чужой | другой гость | — | 404 |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `ordering/orders.py` -- `repeat`
- [x] `http/orders.py` -- `POST /orders/{id}/repeat`
- [x] `webapp/src/guest/HistoryScreen.tsx`, `CartScreen.tsx` (пропущенные)
- [x] тесты `test_history.py`

## Implementation Notes

- Агент принял решения сам. Проверено в браузере локально: «Повторить» собрал корзину с сиропом и количеством.

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | Повтор при уже непустой корзине суммирует количество | low | Ожидаемо: корзина — общая | defer: принято |
