---
title: 'Story 5.2: Оформление доставки по ЖК'
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

**Problem:** Гость хочет заказать доставку домой в пределах ЖК.

**Approach:** На оформлении «Самовывоз / Доставка · N ₽». Для доставки обязательны дом/корпус и квартира, необязательны подъезд, этаж, комментарий курьеру; при наличных — «Сдача с». Стоимость доставки из настроек добавляется к сумме заказа (`delivery_fee`), адрес хранится в заказе, карточка на доске помечена «Доставка».

## Boundaries & Constraints

**Always:** без дома и квартиры — `address_required`; «сдача с» — только наличными и не меньше суммы (`bad_change`); доставка выключена или на паузе — `delivery_unavailable`.

**Never:** геокодирования и зон за пределами ЖК.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Доставка | адрес, наличные, сдача с 5000 | сумма + 150 ₽, адрес и сдача в заказе и на доске | — |
| Без адреса | — | — | 422 `address_required` |
| Сдача меньше суммы | 1 ₽ | — | 422 `bad_change` |
| Сдача при оплате картой | — | — | 422 `bad_change` |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `ordering/{models,orders}.py` -- адрес, сдача, стоимость доставки
- [x] `http/{checkout,orders}.py`
- [x] `webapp/src/guest/CheckoutScreen.tsx`, `OrderScreen.tsx`
- [x] тесты

## Implementation Notes

- Агент принял решения сам.


## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | blind | Цена доставки могла бы меняться между экраном и оформлением | low | Берётся из настроек в момент оформления, снимок в заказе | patch |
