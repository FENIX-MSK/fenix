---
title: 'Story 3.6: Служебный чат и уведомления персоналу'
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

**Problem:** Заказ должны видеть все сотрудники, даже если доска на планшете закрыта.

**Approach:** Сотрудник добавляет бота в группу и пишет `/bind` — группа становится служебным чатом точки (`notifications_staff_chats`, одна на точку). На переход в `new` (`placed` с оплатой на месте, `payment_confirmed`, `released`) подписчик `notifications.staff` шлёт «Новый заказ #NNN — самовывоз, N ₽» с составом и кнопкой. Кнопки Mini App в группах запрещены, поэтому кнопка ведёт в личный чат бота (`?start=order_<id>`), а бот отвечает кнопкой, открывающей доску на этом заказе.

## Boundaries & Constraints

**Always:** `/bind` — только сотрудник точки; повторная привязка заменяет прежний чат; переезд группы в супергруппу сохраняет привязку; ссылка из чата отказывает не-сотрудникам; доставка с повторами (3.4).

**Never:** персональных данных гостя (телефона) в групповом сообщении.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Привязка | `/bind` сотрудником в группе | «Готово: сюда будут приходить новые заказы.» | — |
| Замена | `/bind` в другой группе | «…теперь приходят сюда, а не в прежний чат.» | — |
| Не сотрудник | `/bind` гостем | «Привязать чат может только сотрудник кафе.» | — |
| В личке | `/bind` в личном чате | подсказка про группу | — |
| Новый заказ | переход в `new` | сообщение с кнопкой `t.me/<bot>?start=order_<id>` | нет чата → лог `no_staff_chat` |
| Ссылка | `/start order_<id>` сотрудником | кнопка «Открыть заказ» → `?order=<id>&staff=1` | гостю — отказ |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `notifications/{models,staff_chat}.py` -- служебный чат точки
- [x] `telegram/handlers/staff_chat.py` -- `/bind`, миграция группы
- [x] `telegram/handlers/start.py` -- `order_<id>`
- [x] тесты `test_staff_chat.py`, `test_order_flow.py`

## Implementation Notes

- Агент принял решения сам.
- Комментарий гостя в сообщении есть (кухне он нужен), телефона нет.

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge | Группа стала супергруппой — старый id перестаёт работать | medium | Telegram меняет chat_id | patch: обработчик `migrate_to_chat_id` |
