---
title: 'Story 2.2: Список и отключение сотрудников'
type: 'feature'
created: '2026-10-17'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/implementation-artifacts/spec-2-1-first-staff-and-invitations.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Сотрудники не видят, у кого есть доступ к разделу персонала, и не могут отозвать его у уволившегося коллеги.

**Approach:** Экран «Сотрудники» показывает активных сотрудников точки и позволяет отключить коллегу; отключение действует на следующем же запросе, а последнего активного сотрудника отключить нельзя (FR-35).

## Boundaries & Constraints

**Always:** отключение — мягкое (`is_active=false`, `disabled_at`), повторное приглашение включает обратно; подтверждение отключения вторым нажатием; проверка «последний сотрудник» под той же блокировкой точки, что и bootstrap; можно отключить и себя, если вы не последний.

**Never:** удаление пользователя или его данных; роли.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Список | 2 активных, 1 отключённый | 2 записи: имя, username, дата добавления, признак «это вы» | — |
| Отключение | `POST /api/v1/staff/members/{user_id}/disable` | 200; следующий запрос отключённого к `/staff/*` — 403 | — |
| Последний | единственный активный отключает себя | 409 `last_staff_member` | единый формат |
| Не сотрудник | id пользователя без членства или уже отключённого | 404 `staff_member_not_found` | единый формат |

</frozen-after-approval>

## Code Map

- `backend/src/fenix/modules/identity/{staff,api}.py` -- членство, `_lock_key`
- `backend/src/fenix/http/staff.py` -- роутер персонала
- `webapp/src/staff/StaffMembersScreen.tsx` -- сейчас только приглашение

## Tasks & Acceptance

**Execution:**
- [x] `identity/{staff,api}.py` -- `list_staff`, `disable_staff` (`LastStaffMemberError`, `StaffMemberNotFoundError`)
- [x] `http/staff.py` -- `GET /staff/members`, `POST /staff/members/{user_id}/disable`
- [x] `webapp/src/staff/StaffMembersScreen.tsx` -- список, «Отключить» → «Точно отключить?», ошибки
- [x] тесты матрицы

**Acceptance Criteria:**
- Given отключённый сотрудник, when он открывает Mini App, then кнопки «Персонал» нет

## Implementation Notes

- Отключение под той же advisory-блокировкой точки, что и bootstrap: два сотрудника, отключающие друг друга одновременно, не оставят точку без персонала.
- Отключённый теряет доступ на следующем запросе: `current_staff` проверяет членство на каждом запросе; `/api/v1/me` → `is_staff: false`, кнопка «Персонал» пропадает.
- UI: список (имя, @username, «с 17 октября 2026 г.», «это вы»), «Отключить» → «Точно отключить?», ошибки «Нельзя отключить последнего сотрудника» / «Не сохранилось…».

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge-case | Сетевая ошибка при отключении считалась успехом (строка исчезала) | medium | `.catch` возвращал `error: undefined` | patch: try/catch, ошибка «Не сохранилось» |
| 2 | edge-case | Гонка двух взаимных отключений | low | Без блокировки оба прошли бы проверку «не последний» | patch: advisory-lock точки |

## Verification

**Commands:**
- `cd backend && uv run pytest && uv run mypy && uv run lint-imports` -- expected: зелёное
- `cd webapp && npm run gen:api && npm run lint && npm run build` -- expected: без ошибок
