---
name: Феникс бистро
description: Визуальная система Mini App «Феникс бистро» для гостей и персонала — бордовый и золото из печатного меню, светлая и тёмная тема Telegram.
status: final
updated: 2026-10-16
sources:
  - imports/menu-page-1.png
  - imports/menu-page-2.png
  - ../../prds/prd-fenix-2026-10-16/prd.md
colors:
  # light theme (Telegram light)
  bg: '#F7EFE3'
  surface: '#FFFFFF'
  surface-sunken: '#EFE4D4'
  text: '#3A0B0E'
  text-muted: '#74574A'
  accent: '#731419'
  on-accent: '#F7EFE3'
  gold: '#B8894A'
  gold-text: '#8A6430'
  line: '#E2CFB6'
  error: '#A01B1B'
  # dark theme (Telegram dark)
  bg-dark: '#2B0B0E'
  surface-dark: '#3E1216'
  surface-sunken-dark: '#220809'
  text-dark: '#F3E6D0'
  text-muted-dark: '#BFA088'
  accent-dark: '#D4A96A'
  on-accent-dark: '#2B0B0E'
  gold-dark: '#D4A96A'
  line-dark: '#5A2A28'
  error-dark: '#FF9A8A'
  # order status (badge background / text), light and dark
  status-new: '#F6DEDB'
  status-new-text: '#731419'
  status-cooking: '#F8E6C4'
  status-cooking-text: '#7A4A00'
  status-ready: '#DCEFD9'
  status-ready-text: '#1E5B2E'
  status-delivery: '#DCE8F5'
  status-delivery-text: '#1F4E79'
  status-closed: '#E7E3DE'
  status-closed-text: '#555049'
  status-new-dark: '#6B1A20'
  status-new-text-dark: '#F3E6D0'
  status-cooking-dark: '#4A3210'
  status-cooking-text-dark: '#F8D9A0'
  status-ready-dark: '#1C3A22'
  status-ready-text-dark: '#BFE6BF'
  status-delivery-dark: '#1B3048'
  status-delivery-text-dark: '#BFD8F2'
  status-closed-dark: '#3A3432'
  status-closed-text-dark: '#CFC8C0'
typography:
  display:
    fontFamily: "'Tenor Sans', system-ui, sans-serif"
    fontSize: 28px
    lineHeight: 1.15
    letterSpacing: 0.14em
  title:
    fontFamily: "'Tenor Sans', system-ui, sans-serif"
    fontSize: 20px
    lineHeight: 1.2
    letterSpacing: 0.12em
  section:
    fontFamily: "'Tenor Sans', system-ui, sans-serif"
    fontSize: 15px
    lineHeight: 1.3
    letterSpacing: 0.14em
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 15px
    lineHeight: 1.4
  body-strong:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 15px
    fontWeight: 600
    lineHeight: 1.35
  caption:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 12px
    lineHeight: 1.35
  price:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 15px
    fontWeight: 600
  order-number:
    fontFamily: "'Tenor Sans', system-ui, sans-serif"
    fontSize: 32px
    letterSpacing: 0.08em
rounded:
  sm: 6px
  md: 12px
  lg: 16px
  xl: 20px
  full: 9999px
spacing:
  '1': 4px
  '2': 8px
  '3': 12px
  '4': 16px
  '5': 20px
  '6': 24px
  '8': 32px
  gutter: 16px
  tap-min: 44px
components:
  category-chip:
    background: transparent
    border: '{colors.line}'
    text: '{colors.text}'
    background-selected: '{colors.accent}'
    text-selected: '{colors.on-accent}'
    radius: '{rounded.full}'
    typography: '{typography.caption}'
  dish-card:
    background: '{colors.surface}'
    radius: '{rounded.md}'
    padding: '{spacing.3}'
    photo-size: 72px
    photo-radius: '{rounded.sm}'
    title: '{typography.body-strong}'
    meta: '{typography.caption}'
    price: '{typography.price}'
  sold-out-badge:
    border: '{colors.line}'
    text: '{colors.text-muted}'
    radius: '{rounded.sm}'
  option-row:
    background: '{colors.surface}'
    selected-mark: '{colors.accent}'
    disabled-text: '{colors.text-muted}'
  primary-button:
    background: '{colors.accent}'
    text: '{colors.on-accent}'
    radius: '{rounded.md}'
    height: 48px
  secondary-button:
    background: transparent
    border: '{colors.accent}'
    text: '{colors.accent}'
    radius: '{rounded.md}'
  cart-bar:
    background: '{colors.accent}'
    text: '{colors.on-accent}'
    radius: '{rounded.md}'
  status-badge:
    radius: '{rounded.full}'
    typography: '{typography.caption}'
  order-card:
    background: '{colors.surface}'
    radius: '{rounded.lg}'
    padding: '{spacing.4}'
    number: '{typography.title}'
  divider-ornament:
    color: '{colors.gold}'
  status-steps:
    track: '{colors.line}'
    done: '{colors.accent}'
    current-label: '{typography.body-strong}'
    label: '{typography.caption}'
  promo-banner:
    border: '{colors.gold}'
    text: '{colors.gold-text}'
    radius: '{rounded.md}'
  active-order-bar:
    background: '{colors.surface}'
    border: '{colors.accent}'
    radius: '{rounded.md}'
  quantity-stepper:
    border: '{colors.line}'
    icon: '{colors.accent}'
    radius: '{rounded.full}'
    height: 36px
  bottom-nav:
    background: '{colors.bg}'
    border-top: '{colors.line}'
    active: '{colors.accent}'
    inactive: '{colors.text-muted}'
  skeleton:
    background: '{colors.surface-sunken}'
    radius: '{rounded.md}'
  connection-banner:
    background: '{colors.text}'
    text: '{colors.bg}'
  kitchen-load:
    dot-calm: '{colors.status-ready-text}'
    dot-busy: '{colors.status-cooking-text}'
    dot-high: '{colors.accent}'
    text: '{typography.caption}'
  reason-sheet:
    background: '{colors.surface}'
    radius: '{rounded.xl}'
---

# Феникс бистро — визуальная система

## Brand & Style

Визуальный язык — продолжение печатного меню кафе ([страница 1](imports/menu-page-1.png), [страница 2](imports/menu-page-2.png)): глубокий бордовый, тёплое золото, строгие заголовки капителью с разрядкой, лаконичные описания. Настроение — «уютное бистро с характером»: тепло и празднично, но без вычурности; еда и цена всегда важнее декора.

Приложение следует теме Telegram пользователя (каждый токен `x` в тёмной теме заменяется парным `x-dark`; статусы — `status-*-dark`): в светлой — кремовый фон с бордовыми акцентами, в тёмной — бордово-чёрный фон с золотом. Раздел персонала использует ту же систему, без отдельного «рабочего» стиля.

## Colors

- **`{colors.accent}` / `{colors.accent-dark}`** — главный цвет действия: основная кнопка, выбранная категория, полоса корзины, цены. В светлой теме — бордовый из меню, в тёмной — золото из меню.
- **`{colors.bg}` / `{colors.bg-dark}`** — фон экрана: кремовый, как бумага меню на свету, и бордово-чёрный, как фон меню в полутьме.
- **`{colors.surface}`** — карточки блюд, заказов, листы выбора.
- **`{colors.gold}`** — только декор в светлой теме: тонкие линии, рамки, орнамент-разделитель. **Не для текста** (контраст 2.7:1). Золотой текст в светлой теме — `{colors.gold-text}` (4.7:1).
- **`{colors.text-muted}`** — вес, состав, подписи; контраст ≥5.7:1 в обеих темах.
- **Статусы заказа** (`status-*`) — приглушённые тона, различимые на доске: новый — бордовый, готовится — янтарь, готов — зелёный, в доставке — синий, выдан/отменён — серый. Все пары текст/фон ≥6:1.
- **`{colors.error}`** — ошибки форм и сбои оплаты; не используется для «Закончилось» (это нейтральное состояние).

Все основные пары проходят WCAG AA для текста; основной текст и акцент — AAA.

## Typography

- **Tenor Sans** — логотип «ФЕНИКС», заголовки экранов, названия категорий, номер заказа. Всегда заглавными с разрядкой (`{typography.display}`, `{typography.title}`, `{typography.section}`). Загружается один начертанием с кириллическим подмножеством.
- **Системный шрифт** — всё остальное: названия блюд, описания, цены, кнопки, формы (`{typography.body}`, `{typography.body-strong}`, `{typography.caption}`, `{typography.price}`). Не грузится по сети — экран открывается быстрее (NFR-1).
- Названия блюд — обычным регистром, не капителью: их много, и капитель утомляет при чтении списка.
- Номер заказа на экране гостя — крупно, `{typography.order-number}`: его называют на кассе.

## Layout & Spacing

- Шкала отступов кратна 4 px; поля экрана `{spacing.gutter}`.
- Минимальная зона нажатия `{spacing.tap-min}`.
- Телефон (360–767 px): одна колонка карточек, карусель категорий прилипает под шапкой, полоса корзины — внизу над безопасной зоной.
- Планшет (≥768 px), раздел персонала: доска заказов в колонках по статусам; гостевые экраны — карточки в две колонки.

## Elevation & Depth

Почти плоско. Глубина передаётся тоном (`surface` на `bg`), а не тенями. Единственная тень — у нижнего листа выбора блюда и у полосы корзины, чтобы они читались поверх списка. В тёмной теме тени не используются, только тон.

## Shapes

Скругления мягкие, но не «пузырчатые»: карточки `{rounded.md}`, листы и карточки заказов `{rounded.lg}`, чипсы категорий и статусы — `{rounded.full}`, фото блюд `{rounded.sm}`. Орнамент из меню (лучи солнца-феникса) — только в шапке главного экрана и на пустых состояниях, тонкой линией `{colors.gold}`.

## Components

- **Чипс категории** — контурный, выбранный залит `{colors.accent}`.
- **Карточка блюда** — фото слева (72 px, заглушка с силуэтом лучей, пока фото нет), справа название, вес/состав в одну-две строки, цена «от N ₽». Позиция из стоп-листа — приглушена, с меткой «Закончилось».
- **Лист блюда** — выезжает снизу: большое фото, название, состав, группы выбора (радио для «один из», чекбоксы для добавок, доплата справа), количество, итог.
- **Основная кнопка** — `{colors.accent}`, высота 48 px; в Telegram дублируется нативной MainButton с теми же цветами.
- **Полоса корзины** — внизу, «Корзина · N ₽», цвет основной кнопки.
- **Статус-бейдж** — пилюля с цветом статуса.
- **Карточка заказа (персонал)** — номер крупно Tenor Sans, время и тип получения, бейдж статуса, состав с модификаторами, оплата, кнопка следующего действия на всю ширину.
- **Орнамент-разделитель** — тонкая золотая линия с лучами, только декоративно.
- **Лента статуса** — 4 точки на линии `{colors.line}`; пройденные и текущая — `{colors.accent}`, подпись текущего шага жирная.
- **Баннер акции** — контур `{colors.gold}`, текст `{colors.gold-text}`, без заливки; одна строка, максимум две.
- **Плашка активного заказа** — над списком меню: номер, статус-бейдж, стрелка; контур `{colors.accent}`.
- **Счётчик количества** — «−  N  +» в пилюле, иконки `{colors.accent}`, высота 36 px (зона нажатия 44 px).
- **Нижняя навигация персонала** — 4 пункта, активный `{colors.accent}`, подписи всегда видны.
- **Скелетон** — блоки `{colors.surface-sunken}` в форме карточек, без мерцания при «уменьшить движение».
- **Баннер связи** — тонкая полоса сверху, инверсные цвета `{colors.text}` / `{colors.bg}`.
- **Индикатор загруженности кухни** — тихая строка в шапке: точка 8 px (спокойно — зелёный, умеренно — янтарь, загружено — `{colors.accent}`) и текст `{typography.caption}` цвета `{colors.text-muted}`: «Готовим ≈20 мин». На уровне «загружено» текст «Кухня загружена · ≈40 мин» цвета `{colors.text}`. Без плашек, рамок и анимации. У персонала — то же в шапке доски с числом заказов в работе.
- **Лист причин отмены** — нижний лист `{rounded.xl}`, список причин и поле «Другое».

Макеты: [ключевые экраны](mockups/key-screens.html), [выбор палитры](mockups/color-themes.html), [выбор шрифта](mockups/typography.html). При расхождении с макетами прав этот документ.

## Do's and Don'ts

- **Do** брать цвета только из токенов; новые оттенки — через DESIGN.md.
- **Do** проверять каждый новый экран в светлой и тёмной теме Telegram.
- **Don't** использовать `{colors.gold}` для текста в светлой теме.
- **Don't** набирать капителью Tenor Sans длинные тексты, названия блюд и кнопки.
- **Don't** использовать красный `{colors.error}` для «Закончилось» и отмен — это не ошибки гостя.
- **Don't** добавлять тени и градиенты сверх описанных.
