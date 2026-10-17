---
title: 'Story 5.1: Параметры заказа в настройках'
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

**Problem:** Условия заказа должны соответствовать реальной работе кафе.

**Approach:** «Ещё → Приём заказов, доставка, параметры»: время приготовления (20), шаг слотов (15), таймаут оплаты (15), доставка вкл./выкл. и её стоимость, пороги и добавки загруженности. `GET/PUT /api/v1/staff/location/order-params`; новые значения читаются при каждом оформлении, поэтому действуют для заказов после сохранения (FR-31).

## Boundaries & Constraints

**Always:** проверка диапазонов (`bad_params`): шаг из 5/10/15/20/30/60, пороги и добавки по возрастанию; только персонал.

**Never:** пересчёта уже созданных заказов.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Сохранить | prep 30, доставка 200 ₽ | «Как можно скорее (≈30 мин)», доставка 200 ₽ | — |
| Неверный шаг | 7 мин | — | 422 `bad_params` |
| Гость | — | — | 403 |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `locations/{models,settings,api}.py` + миграция 0010
- [x] `http/staff_location.py`, `webapp/src/staff/OrderSettingsScreen.tsx`
- [x] тесты `test_delivery_preorders.py`

## Implementation Notes

- Агент принял решения сам.
- Стоимость доставки по умолчанию — заглушка 150 ₽ (данные кафе — заглушки, решение по эпику 1).

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | Пороги «умеренно» ≥ «загружено» | low | Уровни перепутаются | patch: валидация |
