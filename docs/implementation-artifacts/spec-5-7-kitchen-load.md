---
title: 'Story 5.7: Загруженность кухни и время ожидания'
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

**Problem:** В час пик гость должен знать честное время ожидания.

**Approach:** `ordering.api.kitchen_load`: заказы в `new/accepted/cooking`; до порога «умеренно» — «спокойно», дальше «умеренно», от порога «загружено» — «загружено»; добавки 0/+10/+20 мин из настроек. Гость видит «Готовим ≈M мин» / «Кухня загружена» в шапке (обновление раз в минуту) и в «Как можно скорее»; ранний слот не раньше этого времени. Сотрудник задаёт уровень вручную на 30/60 мин или до отмены (индикатор в шапке доски), событие `locations.kitchen.load_changed` сразу обновляет все доски.

## Boundaries & Constraints

**Always:** ручной уровень истекает сам; «загружено» не блокирует оформление.

**Never:** блокировки заказов по загрузке.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Авто | 4 в работе | «умеренно», ≈30 мин | — |
| Вручную | «загружены», 30 мин | ≈40 мин, «Кухня загружена» | — |
| Истёк срок | через 31 мин | снова авто | — |
| Вернуть авто | level null | авто | — |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `ordering/kitchen.py`, `locations/settings.py`
- [x] `http/staff_orders.py` -- `POST /staff/orders/kitchen`, `kitchen` в доске
- [x] `Board.tsx` -- индикатор и лист, `Header.tsx`, `useLocationInfo.ts`
- [x] тесты

## Implementation Notes

- Агент принял решения сам.


## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | Сигнал о смене уровня не содержит заказа | low | Realtime-обработчик требовал `order_id` | patch: канал персонала без `order_id` |
