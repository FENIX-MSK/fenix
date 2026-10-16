# Deferred Work

- source_spec: `docs/implementation-artifacts/spec-1-1-module-skeleton.md`
  summary: Направить логи uvicorn (access и error) через structlog JSON и убрать двойной трейс при 500 (`http.unhandled_error` + «Exception in ASGI application»).
  evidence: Воспроизведено локально на uvicorn: Starlette `ServerErrorMiddleware` перевыбрасывает исключение после обработчика, uvicorn пишет его второй раз обычным текстом мимо JSON.
- source_spec: `docs/implementation-artifacts/spec-1-1-module-skeleton.md`
  summary: Убрать из инфраструктуры остатки webhook — маршрут `/telegram/webhook` в `infra/caddy/Caddyfile`, переменные `PUBLIC_BASE_URL`/`TELEGRAM_WEBHOOK_SECRET` в `infra/.env.example`, комментарий про `TELEGRAM_BOT_MODE` в `infra/compose.prod.yaml`.
  evidence: История 1.1 удалила webhook из API (AD-8), но её intent запрещает трогать инфраструктуру стенда; маршрут Caddy теперь ведёт на 404.
- source_spec: `docs/implementation-artifacts/spec-1-1-module-skeleton.md`
  summary: Не сбрасывать накопившиеся обновления Telegram при рестарте бота (`delete_webhook(drop_pending_updates=True)` в `telegram/polling.py`).
  evidence: Polling теперь единственный режим и в продакшене; сообщения гостей, пришедшие во время рестарта сервиса `bot`, теряются.
- source_spec: `docs/implementation-artifacts/spec-1-3-location-hours-and-info.md`
  summary: Применять смену темы Telegram во время работы Mini App (событие `theme_changed`).
  evidence: Тема читается один раз при запуске в `App.tsx` (`useTheme`).
- source_spec: `docs/implementation-artifacts/spec-1-3-location-hours-and-info.md`
  summary: Проверять IANA-пояс и часы работы при редактировании точки (история 2.7).
  evidence: `ZoneInfo` с неверным именем бросает исключение, и `/api/v1/location` ответит 500.
- source_spec: `docs/implementation-artifacts/spec-1-5-guest-browses-menu.md`
  summary: Добавить тестовый раннер Mini App (например, Vitest + Testing Library) и покрыть карточку блюда, «Закончилось» и форматирование цены.
  evidence: Поведение экрана меню проверено только вручную в браузере; в `webapp` нет тестов.
