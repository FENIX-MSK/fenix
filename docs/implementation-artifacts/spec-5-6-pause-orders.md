---
title: 'Story 5.6: Приостановка приёма заказов и доставки'
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

**Problem:** Кафе не должно принимать то, что не выполнит.

**Approach:** Переключатели «Приём заказов приостановлен» и «Доставка приостановлена» в настройках персонала (`PUT /api/v1/staff/location/pauses`). Гость видит пояснение на оформлении и в шапке; сервер отклоняет `orders_paused` / `delivery_unavailable`.

## Boundaries & Constraints

**Always:** уже принятые заказы не затронуты.

**Never:** автоматического снятия паузы.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Пауза доставки | — | только самовывоз, «Доставка сейчас приостановлена» | 422 `delivery_unavailable` |
| Пауза приёма | — | «Сейчас кафе не принимает заказы» | 422 `orders_paused` |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `locations/settings.py` -- паузы
- [x] `http/staff_location.py`, `checkout.py`, `location.py`
- [x] `OrderSettingsScreen.tsx`, `CheckoutScreen.tsx`, `Header.tsx`
- [x] тесты

## Implementation Notes

- Агент принял решения сам.


## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | blind | Пауза не видна гостю до оформления | low | Шапка обновляется раз в минуту | patch: статус в шапке |
