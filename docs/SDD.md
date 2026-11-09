# System Design Document (SDD)
## Telegram AI Repost & Publishing Pipeline Bot

- **Project Name:** Telegram AI Repost & Publishing Pipeline Bot
- **Version:** 1.1.0
- **Author:** Pair Programming (User & Antigravity)
- **Date:** 2026-11-04
- **Status:** Approved (Hardened & Settings Extension)

---

## 1. Purpose & Goals
- **Business Goal:** Предоставить владельцу Telegram-канала автономного, но контролируемого ассистента для публикации новостей и статей. Конвейер принимает ссылку или сырой текст, защищает от дубликатов, извлекает чистый текст, переписывает его в динамичном живом стиле через LLM с сохранением всех фактов и цифр, генерирует релевантную обложку и отправляет интерактивный черновик на утверждение автору в Telegram ЛС. Только после нажатия кнопки «Опубликовать» пост размещается в канале.
- **Интерактивное управление настройками:** Встроенное меню `/settings` в Telegram для оперативного переключения тональности, модели генерации картинок, просмотра привязанного канала и управления хэштегами без правки серверных файлов.
- **Success Criteria:**
  - Дедупликация 100% повторно отправленных ссылок/текстов с возможностью перезапуска незавершённых задач.
  - Асинхронная неблокирующая очередь обработки (In-Memory Worker Queue): мгновенный ответ бота пользователю (< 200 мс).
  - Устойчивость к падению внешних AI API: автоматический fallback на резервную модель, ротация моделей генерации картинок (`gpt-image-2.5-flare`, `gpt-image-1`, `gpt-image-2`) и санитизация чувствительных триггеров.
  - Устойчивый парсинг веб-страниц: защитный лимит на размер HTML (1.5 МБ), обход защиты от ботов через резервный прокси Jina Reader.
  - Защита хранилища: автоматическая ротация локальных изображений с TTL 14 дней.
  - Zero hallucination leak: ни один пост не публикуется в канал без ручного одобрения владельца (human-in-the-loop).
  - 100% покрытие ключевых сценариев unit-, integration- и e2e-тестами.
- **Out of Scope (v1.1):** Мультиканальная маршрутизация по категориям (запланировано в будущем), платная подписка.

---

## 2. Domain Model
*(Подробное описание в `docs/DDD.md`)*
### 2.1 Core Entities & Aggregates
- **Aggregate Root:** `PublishingJob`
  - ID: `UUID`
  - Invariants: `AWAITING_APPROVAL` требует наличия `PostContent`; `PUBLISHED` требует флага `is_approved=True`.
- **Entity:** `UserSettings`
  - `user_id`: ID пользователя Telegram.
  - `preferred_tone`: Тон рерайта (по умолчанию `dynamic`).
  - `preferred_image_model`: Модель генератора картинок.
  - `updated_at`: Временная метка изменения.
- **Value Objects:** `ContentHash`, `Tone`, `JobStatus`, `PostContent`, `ImageAsset`.

---

## 3. System Architecture
### 3.1 High-Level Design (Hexagonal / Clean Architecture)
```
+-------------------------------------------------------------------------------+
|                       Presentation Layer (aiogram 3)                          |
|  - Message Handlers (Raw text, URL commands /rewrite, /settings)              |
|  - Callback Handlers (Moderation buttons, Settings inline menus)              |
+-------------------------------------------------------------------------------+
                                      │  (DTOs / Commands)
                                      ▼
+-------------------------------------------------------------------------------+
|                       Application Layer (Use Cases & Pipeline)                |
|  - PipelineQueueWorker (In-Memory Worker Queue: asyncio.Queue)                |
|  - PipelineOrchestrator (State machine transitions)                           |
|  - SettingsService / StorageManager (TTL Cleanup & Orphan Recovery)           |
+-------------------------------------------------------------------------------+
                                      │  (Ports / Interfaces)
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
+--------------------+      +--------------------+      +--------------------+
| Extractor Adapter  |      |   AI Provider      |      | Persistence        |
| - Trafilatura      |      |   Adapters         |      | - SQLite (WAL)     |
| - BeautifulSoup    |      | - OpenAI/DeepSeek  |      | - aiosqlite +      |
| - Jina Reader Fall |      | - DALL-E / Flare / |      |   busy_timeout     |
| - HTTPX Client     |      |   Sunburst Rotator |      |                    |
+--------------------+      +--------------------+      +--------------------+
```

### 3.2 Technology Stack
- **Language:** Python 3.12+ / 3.14+
- **Bot Framework:** aiogram 3.17+
- **Database:** SQLite 3 with WAL mode via `aiosqlite` with strict connection pooling & `busy_timeout = 5000`
- **AI Clients:** OpenAI SDK (OpenAI API, DeepSeek API, and OpenAI-compatible gateways like `cheapvibecode.ru`)
- **Scraper:** `trafilatura` + `httpx` + `beautifulsoup4` + `Jina Reader API fallback`
- **Image Generation & Storage:** Двухуровневая генерация обложек: основной DALL-E/OpenAI rotator (`gpt-image-2`, `dall-e-3`) + автономный `PollinationsImageGenerator` (Flux/SD) fallback (ADR-018) с динамическим `seed`, гарантированной генерацией новой ИИ-обложки для каждого материала (ADR-019) и обязательным использованием ключевых сущностей, технологий и объектов из статьи (ADR-020); хранилище `storage/images/` с TTL-очисткой 14 дней.
- **Testing:** `pytest`, `pytest-asyncio`, `pytest-mock`

---

## 4. API & Interaction Specification
### 4.1 Telegram Bot Commands & Content Ingestion
- `/start` - Приветствие и справка по работе.
- `/help` - Инструкция по командам и доступным стилям рерайта.
- `/tone` - Выбор желаемого стиля рерайта (`casual`, `formal`, `dynamic`, `humorous`, `analytical`).
- `[URL]` или `[Текст]` - Автоматическое распознавание ссылки или текста и постановка в конвейер.
- **Telegram Posts & Forwards:** Автоматическое извлечение ссылок из `message.entities` (`text_link`) и `message.forward_origin`, резолв исходного канала и статьи-первоисточника.

### 4.2 Interactive Inline Keyboard Actions
- `cb:approve:{job_id}` - Утвердить пост и немедленно опубликовать в целевую группу/канал.
- `cb:regen_img:{job_id}` - Перегенерировать изображение по новому запросу/стилю.
- `cb:regen_text:{job_id}` - Переписать текст заново.
- `cb:reject:{job_id}` - Отклонить черновик и отменить публикацию.

---

## 5. Data Models & Schemas
### 5.1 Database Schema (SQLite)
```sql
CREATE TABLE IF NOT EXISTS publishing_jobs (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    source_input TEXT NOT NULL,
    is_url BOOLEAN NOT NULL,
    content_hash TEXT UNIQUE NOT NULL,
    tone TEXT NOT NULL,
    extracted_title TEXT,
    extracted_body TEXT,
    rewritten_title TEXT,
    rewritten_body TEXT,
    hashtags_json TEXT,
    image_url TEXT,
    image_prompt TEXT,
    is_image_placeholder BOOLEAN DEFAULT 0,
    status TEXT NOT NULL,
    channel_message_id INTEGER,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_hash ON publishing_jobs(content_hash);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON publishing_jobs(status);
```

---

## 6. Workflows & State Machine
### 6.1 Happy Path Flow
1. Пользователь присылает ссылку (веб-сайт или `t.me/...`), пересылает сообщение из канала или вставляет текст.
2. Бот санирует входные данные (удаляет переводы строк из URL), вычисляет SHA-256 `content_hash`. Если запись уже существует — уведомляет о дубликате.
3. Бот создает `PublishingJob` в статусе `PENDING` и немедленно отправляет ответ: *"⏳ Принял в работу!"*.
4. **Extractor** извлекает чистый заголовок и тело статьи (статус `EXTRACTING`). При наличии ссылки на Telegram-пост экстрактор считывает виджет, находит первоисточник (Хабр и др.) и скачивает полный текст оригинальной статьи.
5. **Rewriter** отправляет промпт через настроенный шлюз (`cheapvibecode.ru` / OpenAI / DeepSeek), получая: Заголовок, Тело, Хэштеги и 4 креативных варианта обложки (статус `REWRITING`).
6. **Image Generator** синтезирует уникальное изображение через `gpt-image-2` / DALL-E 3 / Pollinations (статус `GENERATING_IMAGE`), используя динамический seed и промпт от LLM с обязательным внедрением ключевых терминов, сущностей и технологий статьи (ADR-019, ADR-020), сохраняет файл локально в `storage/images/`.
7. Бот переходит в статус `AWAITING_APPROVAL` и присылает готовый черновик в ЛС автору единым сообщением: фото с текстом поста в подписи и прикрепленными кнопками модерации (ADR-010). Вторым информационным сообщением бот отправляет 4 варианта концептов обложки.
8. Автор нажимает «🚀 Опубликовать».
9. Бот публикует фото с текстом поста в подписи единым сообщением в канал/группу, переводит задачу в `PUBLISHED` и подтверждает публикацию.

### 6.2 Error & Fallback Scenarios
- **Сбой парсинга URL:** Если `trafilatura` не смогла распарсить страницу, используется fallback на `BeautifulSoup`. При невозможности извлечь текст бот возвращает понятную ошибку и предлагает прислать скопированный текст.
- **Сбой основного LLM API (Timeout/500/401):** Автоматический fallback на резервный провайдер через `CompositeRewriter`.
- **Сбой Image API (ADR-018):** Если основной шлюз не поддерживает генерацию картинок (403 `model_not_allowed`) или исчерпал баланс, `CompositeImageGenerator` мгновенно и бесшовно переключается на автономный `PollinationsImageGenerator`. Если и резервный генератор недоступен, бот переходит на режим публикации текста с предложением 4 вариантов промптов.

---

## 7. Security & Non-Functional Requirements
- **Secrets Management:** Токены `BOT_TOKEN`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY` хранятся исключительно в `.env` с правами доступа `600`.
- **Access Control:** Доступ к боту ограничен списком `ADMIN_IDS`. Запросы от неавторизованных пользователей игнорируются.
- **Sanitization & URL Defense:** Все входные URL валидируются на отсутствие непечатных ASCII-символов (`\n`, `\r`, пробелы) перед передачей в HTTP-клиент во избежание сбоев в `httpx`.
- **Unified Photo & Caption Format (ADR-009, ADR-010):** Посты с изображениями публикуются как единое сообщение (фото + подпись). Объем основного текста строго ограничен (400–700 символов body), а `render_post(max_length=1024)` гарантирует строгое соблюдение лимита Telegram на подписи к медиафайлам (1024 символа). Для длинных текстовых постов без фото реализован безопасный чанкинг через `split_telegram_message`.
- **SQLite Concurrency:** Включение WAL (Write-Ahead Logging) для предотвращения `database is locked`.
- **Telegram Update Preservation & Resilient Retry (ADR-017):** Запуск polling с `drop_pending_updates=False` для предотвращения потери входящих апдейтов при перезагрузках сервиса; автоматический сброс статуса задач из `FAILED` в `PENDING` при повторной отправке пользователем. Поддержка сохранения оригинальных фотографий из пересланных постов.
