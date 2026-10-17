---
title: 'Story 5.5: Запланированные заказы на доске'
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

**Problem:** Предзаказ нужно готовить к времени, а не сразу.

**Approach:** Предзаказ создаётся в `scheduled` (онлайн — после оплаты, переход `schedule`), виден во вкладке «Запланированные». Воркер раз в 20 с переводит заказы со слотом ближе 30 мин в `new` (`release`): звук на доске и «Предзаказ к 19:30 #NNN» в служебном чате. Срок — в заказе (`scheduled_for`), рестарты не мешают (AD-13). «Принять» предлагает время слота.

## Boundaries & Constraints

**Always:** отменённый предзаказ не выпускается; гость получает «запланирован, будет готов к …».

**Never:** таймеров в процессе API.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Создан | слот, наличные | `scheduled`, не в «Новых» | — |
| Оплачен онлайн | слот | `pending_payment` → `scheduled` | — |
| За 30 мин | воркер | `new`, сообщение персоналу | — |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `ordering/orders.py` -- `schedule`, `due_scheduled`
- [x] `worker.py` -- `release_due_preorders`
- [x] доска -- вкладка «Запланированные»
- [x] тесты

## Implementation Notes

- Агент принял решения сам.


## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | Оплаченный предзаказ попал бы сразу в «Новые» | medium | Переход `payment_succeeded` → `new` | patch: отдельный переход `schedule` |
