---
title: 'Story 5.4: Предзаказ на время сегодня'
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

**Problem:** Гость хочет, чтобы заказ был готов к его приходу.

**Approach:** «Когда»: «Как можно скорее (≈M мин)» или слот. Слоты — от «сейчас + время ожидания (приготовление + загруженность)» до закрытия сегодня, по сетке шага от местной полуночи, в поясе точки (AD-11). Устаревший слот при оформлении — 422 `slot_unavailable` с ближайшими слотами.

## Boundaries & Constraints

**Always:** сервер сверяет слот со своим списком; при круглосуточной работе — до конца суток.

**Never:** предзаказа на другие дни.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Слоты | 20:52, закрытие 22:00, шаг 15 | 21:15 … 22:00 | — |
| Закрыто | — | слотов нет | — |
| Устаревший слот | через 5 мин | — | 422 `slot_unavailable` + ближайшие |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `ordering/kitchen.py` -- `slots`
- [x] `http/checkout.py` -- `slots`
- [x] `CheckoutScreen.tsx` -- выбор времени
- [x] тесты

## Implementation Notes

- Агент принял решения сам.


## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | Круглосуточный режим не даёт времени закрытия | medium | Слотов не было бы | patch: до конца местных суток |
