---
title: 'Story 1.6: Карточка блюда с размерами и модификаторами'
type: 'feature'
created: '2026-10-16'
status: 'done'
baseline_commit: '466e72c44a86b3c439003042ae54d5508d40f6b7'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/implementation-artifacts/epic-1-context.md'
  - '{project-root}/docs/planning-artifacts/ux-designs/ux-fenix-2026-10-16/DESIGN.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Гость видит блюдо в списке, но не может выбрать размер, соус, котлету или добавки и узнать итоговую цену.

**Approach:** API отдаёт карточку блюда (размеры, группы модификаторов блюда и категории с доступностью по стоп-листу) и считает цену выбора единственной функцией `catalog.api.price`, отклоняя недопустимый выбор; лист блюда в Mini App показывает выбор и итог с сервера (FR-4, AD-6).

## Boundaries & Constraints

**Always:** цену считает только сервер — клиент не складывает цены даже для отображения; итог = (цена размера + доплаты модификаторов) × количество, в копейках; незаполненная обязательная группа — не ошибка, а `complete: false` со списком групп; недопустимый выбор → 422 `invalid_selection` (`details.reason`); пока ответ расчёта не пришёл, вместо старой цены — индикатор обновления; выбор сверх максимума группы не применяется (короткая вибрация); недоступные опции видны и неактивны; лист закрывается BackButton, свайпом вниз и тапом по фону; от 768 px — модальное окно по центру.

**Never:** добавление в корзину и MainButton «Добавить» (эпик 3); акции в цене (эпик 6); выбор размера по умолчанию, если доступного размера нет.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Простое блюдо | Филадельфия, 1 шт | `complete: true`, итог 69900 | — |
| Размер и добавки | Капучино 400 мл + сироп + молоко, 2 шт | (25000 + 3000 + 10000) × 2 = 76000 | — |
| Нет обязательного | Крылышки без соуса | `complete: false`, `missing_groups: [Соус]`; в листе группа подсвечена, вместо итога «Выберите соус» | — |
| Обязательный выбран | Крылышки + терияки | `complete: true`, 49900 | — |
| Больше максимума | два соуса крылышкам | 422 `invalid_selection` (`too_many`); в листе второй выбор не ставится | — |
| Чужой модификатор | соус крылышек к капучино | 422 `invalid_selection` (`foreign_modifier`) | — |
| Чужой размер | размер другого блюда | 422 `invalid_selection` (`foreign_size`) | — |
| Недоступная опция | размер или модификатор в стоп-листе точки | 422 `invalid_selection` (`unavailable`); в листе опция «Закончилось», неактивна | — |
| Повтор модификатора | один id дважды | 422 `invalid_selection` (`duplicate_modifier`) | — |
| Скрытое / несуществующее блюдо | карточка | 404 `dish_not_found` | единый формат |
| Количество вне 1–99 | `quantity: 0` | 422 `validation_error` | единый формат |

</frozen-after-approval>

## Code Map

- `backend/src/fenix/modules/catalog/{models,menu,api}.py` -- модели, стоп-лист `stopped_size_ids`; добавить карточку и расчёт
- `backend/src/fenix/http/menu.py` -- роуты меню; добавить карточку и расчёт, `ApiError`
- `backend/tests/test_menu_api.py` -- фикстуры `seeded`, `client`, `stop`
- `webapp/src/App.tsx` -- `openDish` пока пустой; `guest/{DishCard,MenuScreen,format,useRemote}.ts(x)`, `index.css`, `platform/*`
- `webapp/src/platform/types.ts` -- добавить вибрацию (`haptic`)

## Tasks & Acceptance

**Execution:**
- [x] `backend/src/fenix/modules/catalog/{dish,pricing,api}.py` -- `get_dish(session, location_id, dish_id)` с группами блюда, затем категории; `price(session, location_id, dish_id, size_id, modifier_ids, quantity) -> Price{unit_price, total_price, complete, missing_groups}`; `InvalidSelection(reason)` -- AD-6
- [x] `backend/src/fenix/http/menu.py` -- `GET /api/v1/menu/dishes/{dish_id}`, `POST /api/v1/menu/price` -- FR-4
- [x] `backend/tests/test_pricing.py`, `test_dish_api.py` -- вся матрица
- [x] `webapp/src/platform/*` -- `haptic('selection' | 'error' | 'success')`
- [x] `webapp/src/guest/{DishSheet,useDishPrice}.ts(x)` + стили -- лист: фото-заглушка, состав, порция, размеры (радио), группы (радио при макс. 1, иначе чекбоксы с «+N ₽»), «обязательно», количество 1–99, итог из `POST /price` (отмена устаревших запросов), подсказка «Выберите …», закрытие -- FR-4
- [x] `webapp/src/App.tsx` -- открытие листа из карточки
- [x] `webapp/src/api/schema.d.ts` -- перегенерировать

**Acceptance Criteria:**
- Given открытый лист «Капучино», when гость выбирает 400 мл и сироп, then итог «280 ₽» приходит с сервера, а во время запроса виден индикатор, не старая цена
- Given лист на 360 px в светлой и тёмной теме, when гость закрывает его BackButton или свайпом вниз, then возвращается к меню на той же позиции прокрутки

## Implementation Notes

- Спека утверждена агентом по поручению пользователя.
- `catalog.api.price` — единственная функция цены (AD-6): размер + доплаты × количество; проверки — чужой размер/модификатор, повтор, сверх максимума, стоп-лист, скрытое блюдо (`InvalidSelectionError(reason)` → 422 `invalid_selection`, `details.reason`). Незаполненный минимум — `complete: false` и `missing_groups`. Группы блюда идут раньше групп категории, каждая один раз.
- `useDishPrice`: ответ засчитывается только для того выбора, для которого запрошен (ключ выбора), прошлые запросы отменяются `AbortController`; пока ответа нет — индикатор, не старая цена. Размер по умолчанию — первый доступный; в обязательных группах автовыбора нет.
- Подсказка «Выберите соус / котлету»: название группы в винительный падеж по окончанию (-а → -у, -я → -ю), достаточно для однословных названий групп.
- Лист: BackButton, свайп вниз за ручку (порог 80 px), тап по фону, Esc; фокус переводится в диалог; прокрутка меню под листом сохраняется. От 768 px — модальное окно по центру.
- MainButton «Добавить» не используется — корзина в эпике 3.
- Проверено в браузере: Капучино 400 мл + сироп = «280 ₽» (с индикатором во время запроса), крылышки — подсказка и подсветка группы, затем «499 ₽»; Black Angus — «Выберите котлету»; закрытие тремя способами; 360 px светлая, 800 px тёмная.

## Spec Change Log

## Review Triage Log

Ревью выполнено inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | blind | «Выберите котлета» — неверный падеж в подсказке | medium | Воспроизведено на Black Angus | patch: винительный падеж по окончанию, текст «Выберите соус» из матрицы сохранён |
| 2 | blind | Фокус не переходит в открытый диалог | low | Экранный диктор и клавиатура остаются в списке под листом | patch: фокус на листе при открытии |
| 3 | edge-case | `setState` в эффекте расчёта цены давал каскадный рендер и мог на мгновение показать прошлую цену | low | Предупреждение oxlint; ответ не был привязан к выбору | patch: ответ хранится с ключом выбора, «ожидание» выводится сравнением ключей |
| 4 | verification-gap | Путь «сверх максимума» в листе не проверен в браузере | low | В меню нет группы, где максимум меньше числа опций (у «Добавок» 2 опции при максимуме 2); серверная проверка покрыта тестом `too_many` | reject: проверится, когда появятся такие группы (редактор, эпик 2) |
| 5 | edge-case | Опция ушла в стоп-лист, пока лист открыт | low | Расчёт вернёт `invalid_selection` → «Этот вариант сейчас недоступен» | reject: поведение корректно, лист не обновляет доступность в реальном времени — это AD-5, эпик 3 |

## Design Notes

Порядок групп в карточке: сначала группы блюда, затем группы категории. Размер по умолчанию — первый доступный (размер выбирается всегда); в обязательных группах модификаторов ничего не выбирается автоматически. Расчёт — `POST` с телом `{dish_id, size_id, modifier_ids, quantity}`; ответ `{unit_price, total_price, complete, missing_groups: [{id, name}]}`; клиент шлёт запрос при каждом изменении, отменяя предыдущий (`AbortController`). Подсказка: «Выберите » + названия недостающих групп в нижнем регистре через « и ».

## Verification

**Commands:**
- `cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest` -- expected: зелёное
- `cd webapp && npm run gen:api && git diff --exit-code src/api/schema.d.ts && npm run lint && npm run build` -- expected: без ошибок

**Manual checks:**
- Лист «Капучино», «Куриные крылышки», «Black Angus» на 360 px в обеих темах; 800 px — модальное окно; закрытие тремя способами
