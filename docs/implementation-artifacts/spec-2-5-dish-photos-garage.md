---
title: 'Story 2.5: Фото блюд в хранилище Garage'
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

**Problem:** У блюд нет фотографий, а хранилище на стенде — MinIO, который перестал публиковать образы.

**Approach:** Заменить MinIO на Garage v2.4.1, поднимаемый без ручных шагов; сотрудник загружает фото с телефона, сервер уменьшает его и кладёт в Garage под новым ключом, гости получают картинку через Caddy по `/media/*` с долгим кешем (FR-27, AD-12).

## Boundaries & Constraints

**Always:** Garage не публикуется наружу; бакет, ключ и website-доступ создаются при развёртывании; принимаются JPEG/PNG/WebP/HEIC до 15 МБ; результат — WebP ≤1280 px по длинной стороне, ~300 КБ, без EXIF; ключ объекта неизменяем; при ошибке загрузки старое фото остаётся.

**Never:** прямой доступ гостей к Garage; хранение исходников.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Фото с телефона | JPEG/PNG/WebP/HEIC 3000×2000 | WebP 1280×853, ~300 КБ, повернуто по EXIF | — |
| Маленькое фото | 400×300 | не увеличивается | — |
| Другой формат | GIF, BMP, текст | 422 `unsupported_image` | старое фото остаётся |
| Больше 15 МБ | 15 МБ + 1 байт | 422 `image_too_large` | старое фото остаётся |
| Гость | меню и карточка | `photo_url: /media/dishes/<id>/<uuid7>.webp` | — |
| Новое фото | повторная загрузка | новый ключ | — |
| Свежий стенд | пустые тома Garage | layout, бакет `media`, ключ, website создаются в `migrate`; повтор ничего не меняет | повтор до минуты, пока Garage стартует |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [x] `infra/{compose.prod,compose.dev}.yaml`, `infra/garage/garage.toml` -- Garage вместо MinIO, тома, без публикации портов на стенде
- [x] `infra/caddy/Caddyfile` -- `handle_path /media/*` → `garage:3902` с `Host: media`
- [x] `.github/workflows/deploy.yml` -- генерация секретов Garage/S3 при отсутствии, выгрузка `infra/garage`, удаление тома MinIO
- [x] `backend/src/fenix/platform/storage.py` -- `S3Storage` (boto3 в потоке), `ensure_bucket` через admin API v2
- [x] `backend/src/fenix/seed.py` -- инициализация хранилища с повторами
- [x] `backend/src/fenix/modules/catalog/photos.py` + `api.py` -- `shrink`, `new_key`, `set_dish_photo`
- [x] `backend/src/fenix/http/{media,staff_catalog,menu}.py` -- загрузка/удаление фото, `photo_url` гостям
- [x] `webapp/src/staff/menu/PhotoField.tsx` -- превью, прогресс, «Повторить», «Убрать фото»; `vite.config.ts` -- прокси `/media`
- [x] тесты матрицы

## Implementation Notes

- Garage проверен локально целиком: admin API v2 (`GetClusterStatus`, `UpdateClusterLayout`, `ApplyClusterLayout`, `CreateBucket`, `ImportKey`, `AllowBucketKey`, `UpdateBucket` с `websiteAccess`), загрузка через S3 (boto3, path-style), раздача web-эндпоинтом по `Host: media` с сохранением `Cache-Control: public, max-age=31536000, immutable`. Первый `fenix-seed` создал всё, второй — `changed=[]`.
- Секреты Garage и ключ S3 генерируются deploy-скриптом один раз (`ensure_secret`), дальше сохраняются в `/opt/fenix/.env`.
- Альфа-канал WebP сжимается без потерь и игнорирует `quality` — PNG с шумовой прозрачностью давал 1,6 МБ. Теперь `alpha_quality`, а если всё ещё больше цели — наложение на белый фон.
- `Image.MAX_IMAGE_PIXELS = 60 млн` — защита от «бомб» декомпрессии; декодирование в `asyncio.to_thread`.
- Старые объекты при замене фото не удаляются (ключи неизменяемы, порядок «сначала объект, потом ссылка»); очистка сирот — отложена.
- Локально в worktree под приватным `/tmp` docker не видит bind-mount конфига Garage — проверял с `docker cp`; в обычном checkout compose работает как есть.

## Spec Change Log

## Review Triage Log

Ревью inline.

| # | Слой | Находка | Вердикт | Обоснование | Маршрут |
|---|------|---------|---------|-------------|---------|
| 1 | edge-case | PNG с прозрачностью давал WebP в 5 раз больше цели | medium | Воспроизведено тестом | patch: `alpha_quality` + наложение на белый |
| 2 | edge-case | «Бомба» декомпрессии | low | Pillow по умолчанию лишь предупреждает до 179 Мп | patch: лимит 60 Мп, ошибка → `unsupported_image` |
| 3 | blind | Объекты прежних фото остаются в бакете | low | Ключи неизменяемы, удаление до коммита рискованно | defer: периодическая очистка неиспользуемых ключей |

## Verification

**Commands:**
- `cd backend && uv run pytest && uv run mypy && uv run lint-imports` -- expected: зелёное
- `docker compose -f infra/compose.dev.yaml up -d garage && cd backend && uv run fenix-seed && uv run fenix-seed` -- expected: второй запуск `changed=[]`
