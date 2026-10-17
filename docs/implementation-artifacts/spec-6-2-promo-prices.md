---
title: 'Story 6.2: Акционные цены в меню и корзине'
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

**Problem:** Гость должен сразу видеть, сколько заплатит.

**Approach:** `catalog.price` применяет к позиции одну акцию — с наибольшей скидкой среди действующих сегодня автоматических (и заявленной «с проверкой»); цена округляется до рубля. Меню, карточка, корзина и заказ показывают старую цену зачёркнутой; позиция заказа хранит снимок (исходная цена, акция). Баннер акций над меню.

## Boundaries & Constraints

**Always:** истёкшая или выключенная акция не применяется без действий сотрудника; сумма заказа = сумма корзины.

**Never:** расчёта цены в Mini App (AD-6).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Авто 20% | Филадельфия | цена −20%, старая зачёркнута, в заказе та же сумма | — |
| 10% всё меню + 30% роллы | ролл / кофе | 30% / 10% | — |
| Истекла | вчера | без скидки | — |
| Выключена | — | без скидки | — |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `catalog/{pricing,menu,dish}.py`
- [x] `ordering/{cart,orders}.py` -- снимок акции
- [x] `http/{menu,cart,orders}.py`
- [x] `DishCard`, `DishSheet`, `CartScreen`, `MenuScreen` (баннер)
- [x] тесты

## Implementation Notes

- Агент принял решения сам.


## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | blind | Копеечные цены после процента | low | Ценники в рублях | patch: округление до рубля |
