---
title: 'Story 4.1: История заказов'
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

**Problem:** Гость хочет помнить, что брал и сколько платил.

**Approach:** «Мои заказы» — иконка в шапке меню; `GET /api/v1/orders` отдаёт только заказы гостя от новых к старым, страницами по 20 с курсором (created_at, id). Карточка: номер, дата, состав, статус, сумма; нажатие открывает экран заказа. Плашка активного заказа над меню (`GET /api/v1/orders/active`), пока заказ не выдан, обновляется по WebSocket (EXPERIENCE.md › IA).

## Boundaries & Constraints

**Always:** чужие заказы не видны; курсор устойчив к новым заказам (keyset, не offset).

**Never:** причины отмены гостю.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Список | 5 заказов, `limit=2` | 3 страницы, порядок от новых, `next_cursor` null на последней | — |
| Чужие | другой гость | пустой список | — |
| Плохой курсор | `cursor=zzz` | — | 422 `bad_cursor` |
| Пусто | нет заказов | «Здесь появятся ваши заказы» | — |
| Активный | заказ не выдан | плашка «Заказ #NNN · статус» над меню | после выдачи/отмены — нет плашки |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `ordering/orders.py` -- `guest_orders`, `active_guest_order`
- [x] `http/orders.py` -- `GET /orders`, `GET /orders/active`
- [x] `webapp/src/guest/{HistoryScreen,ActiveOrderBanner}.tsx`, иконка в `Header.tsx`
- [x] тесты `test_history.py`

## Implementation Notes

- Агент принял решения сам. Проверено в браузере локально.

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | `/orders/active` после `/orders/{id}` ловился бы как UUID | low | Порядок роутов | patch: объявлен раньше |
