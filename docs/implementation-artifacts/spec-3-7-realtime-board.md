---
title: 'Story 3.7: Доска заказов в реальном времени'
type: 'feature'
created: '2026-10-17'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/planning-artifacts/architecture/architecture-fenix-2026-10-16/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Сотрудник должен видеть все активные заказы и слышать новые, чтобы ни один не потерялся.

**Approach:** Вкладка «Заказы» в разделе персонала: `GET /api/v1/staff/orders` — колонки «Новые / Готовятся / Готовы» (на телефоне — вкладки). Обновления — WebSocket `/api/v1/ws`, канал `staff:<location_id>`: первым сообщением `initData`, дальше только сигналы; клиент перечитывает доску через REST. Воркер публикует сигналы в Redis (AD-5). Новый заказ — звук (Web Audio, включается одним нажатием), вибрация и подсветка на 5 с; сигнал повторяется каждые 30 с, пока новый заказ не открыт и не принят.

## Boundaries & Constraints

**Always:** канал персонала — только сотрудникам (4403), чужой заказ — 4403, плохой `initData` — 4401; после обрыва — переподключение с паузой до 15 с и перечитывание доски; страховочный опрос раз в 30 с.

**Never:** состояния в сообщениях WS (только сигнал).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Загрузка | сотрудник | колонки, карточка: номер, время, состав с модификаторами, комментарий, способ и статус оплаты | гость → 403 |
| Новый заказ | доска открыта | появляется ≤ 5 с (замер: 1,8 с), звук, подсветка | — |
| Ссылка из чата | `?order=<id>&staff=1` | доска с открытой карточкой | заказ ушёл с доски — карточка из `GET /staff/orders/{id}` |
| Обрыв связи | сокет закрылся | переподключение, перечитывание | — |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `platform/realtime.py`, подписчик `realtime.signal` в `worker.py`
- [x] `http/ws.py` -- `/api/v1/ws`; Redis в `app.state`
- [x] `http/staff_orders.py` -- доска и карточка
- [x] `webapp/src/api/signals.ts`, `webapp/src/staff/orders/*` -- доска, карточка, звук
- [x] тесты `test_ws.py`, `test_order_flow.py`; смоук `order-realtime` через Caddy

## Implementation Notes

- Агент принял решения сам.
- Колонка «В доставке» и «Запланированные» добавятся в эпике 5.
- Проверено в браузере локально: колонки на 800 px, вкладки на 375 px.

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | Прокси обрывает тихий сокет без close | low | Клиент не узнает | patch: ping раз в 25 с + опрос раз в 30 с |
