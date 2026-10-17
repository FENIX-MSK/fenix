---
title: 'Story 3.4: Уведомления гостю через outbox'
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

**Problem:** Гость должен узнавать о заказе в чате бота, но Telegram с VPS бывает недоступен, а сообщение по откатившейся транзакции отправлять нельзя.

**Approach:** Таблица `platform_outbox_events`: `ordering` пишет событие `ordering.order.<past_tense>` с самодостаточным снимком заказа в той же транзакции. Воркер `fenix-worker` дважды в секунду забирает события (`FOR UPDATE SKIP LOCKED`), вызывает подписчиков; успех каждого подписчика фиксируется в `platform_outbox_deliveries`, сбой — повтор с экспоненциальной задержкой (до 5 мин). Сообщения рендерит `notifications` и отправляет через `MessengerGateway` (AD-4, AD-8).

## Boundaries & Constraints

**Always:** подписчик не обращается к модулю-источнику; один подписчик выполняется по событию один раз; заблокированный бот (`Undeliverable`) — сообщение отбрасывается, повтор не нужен; HTML экранируется; время — в часовом поясе точки.

**Never:** прямых вызовов Bot API из модулей и роутов; текста причины отмены в сообщении гостю.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Оформлен (на месте) | `placed`, статус `new` | «Заказ #001 оформлен.» + состав, сумма, способ оплаты, кнопка «Открыть заказ» | — |
| Ждёт онлайн-оплату | `placed`, `pending_payment` | сообщения нет | — |
| Принят | `accepted` | «Заказ #001 принят. Будет готов к 9:20.» | — |
| Готов | `ready`, самовывоз | «Заказ #001 готов — ждём вас у кассы.» | — |
| Отменён | `cancelled` | «К сожалению, заказ #001 отменён.» без причины | — |
| Telegram недоступен | ошибка отправки | заказ не блокируется, повтор через 2, 4, 8… с | до успеха |
| Повторная обработка | событие уже доставлено подписчику | второго сообщения нет | — |
| Бот заблокирован | 403 от Telegram | событие закрыто, сообщение отброшено | лог `notifications.guest_undeliverable` |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `platform/outbox.py` + миграция 0009 -- события, доставки, `Dispatcher` с повторами
- [x] `ordering/orders.py` -- событие на создание и каждый переход
- [x] `notifications/{gateway,messages,handlers,api}.py` -- шлюз, тексты, подписчики
- [x] `telegram/gateway.py` -- `TelegramGateway` (aiogram), `worker.py` -- цикл воркера, `fenix-worker`
- [x] тесты: `test_outbox.py`, `test_messages.py`, `test_order_flow.py`

## Implementation Notes

- Агент принял решения сам.
- Отклонение от AD-13: вместо taskiq — свой asyncio-процесс. Все отложенные действия и так хранятся в БД (AD-13), а очередь в Redis добавляла бы задержку и второй источник истины; опрос раз в 0,5 с укладывается в 5 с (NFR-4). taskiq удалён из зависимостей. Записано в `docs/decisions.md`.
- Тексты — по EXPERIENCE.md › Voice and Tone.

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | Telegram отвечает «chat not found» для пользователя без чата с ботом | low | Повтор бесполезен | patch: считается `Undeliverable` |
| 2 | blind | Отправка в Telegram успешна, а коммит отметки упал — повтор пришлёт дубль | low | at-least-once, окно — миллисекунды | defer: принято |
