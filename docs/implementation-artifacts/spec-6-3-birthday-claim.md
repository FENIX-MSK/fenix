---
title: 'Story 6.3: Скидка «с проверкой» при оформлении'
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

**Problem:** Гость хочет получить скидку в день рождения.

**Approach:** На оформлении — отметка «В день рождения — скидка 10%…»: онлайн-оплата скрывается, сумма показана как предварительная (`preview_total` с сервера). Заказ хранит заявку (`discount_claim`, статус `pending`) и сумму без скидки; заявленная акция конкурирует с автоматическими по правилу «одна, наибольшая». На доске — «🎂 … — проверить документ».

## Boundaries & Constraints

**Always:** с заявкой — только оплата на месте (`claim_requires_on_site`); заявить можно только действующую акцию «с проверкой».

**Never:** проверки даты рождения системой (проверяет сотрудник по документу).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Заявка | наличные | сумма −10%, `pending` | — |
| Онлайн | — | — | 422 `claim_requires_on_site` |
| Авто 15% больше | — | предварительная сумма = обычной | — |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `ordering/orders.py` -- заявка в заказе
- [x] `http/{checkout,orders}.py`
- [x] `CheckoutScreen.tsx`, `OrderCard.tsx`
- [x] тесты

## Implementation Notes

- Агент принял решения сам.


## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | Гость выбрал онлайн, потом отметил скидку | low | Кнопка онлайн исчезает | patch: способ переключается на наличные |
