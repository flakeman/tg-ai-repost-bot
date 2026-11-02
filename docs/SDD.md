# System Design Document (SDD)
## Telegram AI Repost & Publishing Pipeline Bot

- **Project Name:** Telegram AI Repost & Publishing Pipeline Bot
- **Version:** 1.0.0
- **Author:** Pair Programming (User & Antigravity)
- **Date:** 2026-11-02
- **Status:** Approved

---

## 1. Purpose & Goals
- **Business Goal:** Предоставить владельцу Telegram-канала автономного, но контролируемого ассистента для публикации новостей и статей. Конвейер принимает ссылку или сырой текст, защищает от дубликатов, извлекает чистый текст, переписывает его в динамичном живом стиле через LLM с сохранением всех фактов и цифр, генерирует релевантную обложкую и отправляет интерактивный черновик на утверждение автору в Telegram ЛС. Только после нажатия кнопки «Опубликовать» пост размещается в канале.
- **Success Criteria:**
  - Дедупликация 100% повторно отправленных ссылок/текстов.
  - Устойчивость к падению внешних AI API: автоматический fallback на резервную модель, публикация без картинки в случае отказа генератора изображений.
  - Zero hallucination leak: ни один пост не публикуется в канал без ручного одобрения владельца (human-in-the-loop).
  - 100% покрытие ключевых сценариев unit-, integration- и e2e-тестами.
- **Out of Scope (v1):** Мультиканальная маршрутизация по категориям (запланировано в будущем), платная подписка.

---

## 2. Domain Model
*(Подробное описание в `docs/DDD.md`)*
### 2.1 Core Entities & Aggregates
- **Aggregate Root:** `PublishingJob`
  - ID: `UUID`
  - Invariants: `AWAITING_APPROVAL` требует наличия `PostContent`; `PUBLISHED` требует флага `is_approved=True`.
- **Value Objects:** `ContentHash`, `Tone`, `JobStatus`, `PostContent`, `ImageAsset`.

---

## 3. System Architecture
### 3.1 High-Level Design (Hexagonal / Clean Architecture)
```
+-------------------------------------------------------------------------------+
|                       Presentation Layer (aiogram 3)                          |
|  - Message Handlers (Raw text, URL commands /rewrite)                         |
|  - Callback Handlers (Inline buttons: [Опубликовать], [Переделать], etc.)     |
+-------------------------------------------------------------------------------+
                                      │  (DTOs / Commands)
                                      ▼
+-------------------------------------------------------------------------------+
|                       Application Layer (Use Cases & Pipeline)                |
|  - PipelineOrchestrator (State machine transitions)                           |
|  - IngestContentUseCase, ExtractUseCase, RewriteUseCase, ImageGenUseCase      |
|  - ApproveAndPublishUseCase, RegenerateUseCase                                |
+-------------------------------------------------------------------------------+
                                      │  (Ports / Interfaces)
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
+--------------------+      +--------------------+      +--------------------+
| Extractor Adapter  |      |   AI Provider      |      | Persistence        |
| - Trafilatura      |      |   Adapters         |      | - SQLite (WAL)     |
| - BeautifulSoup    |      | - OpenAI/DeepSeek  |      | - aiosqlite        |
| - HTTPX Client     |      | - DALL-E / Flux    |      |                    |
+--------------------+      +--------------------+      +--------------------+
```

### 3.2 Technology Stack
- **Language:** Python 3.14.3
- **Bot Framework:** aiogram 3.17+
- **Database:** SQLite 3 with WAL mode via `aiosqlite`
- **AI Clients:** OpenAI SDK (DeepSeek API and OpenAI endpoints)
- **Scraper:** `trafilatura` + `httpx` + `beautifulsoup4`
- **Testing:** `pytest`, `pytest-asyncio`, `pytest-mock`

---

## 4. API & Interaction Specification
### 4.1 Telegram Bot Commands
- `/start` - Приветствие и справка по работе.
- `/help` - Инструкция по командам и доступным стилям рерайта.
- `/rewrite [tone]` - Запуск обработки с явным выбором стиля (`casual`, `formal`, `dynamic`).
- `[URL]` или `[Текст]` - Автоматическое распознавание ссылки или текста и постановка в очередь.

### 4.2 Interactive Inline Keyboard Actions
- `cb:approve:{job_id}` - Утвердить пост и немедленно опубликовать в канал.
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
1. Пользователь присылает ссылку или текст боту.
2. Бот вычисляет SHA-256 `content_hash`. Если запись уже существует — уведомляет пользователя о дубликате.
3. Бот создает `PublishingJob` в статусе `PENDING` и немедленно отправляет ответ: *"Принял в работу. Обрабатываю..."*.
4. **Extractor** извлекает чистый заголовок и тело статьи (статус `EXTRACTING`).
5. **Rewriter** отправляет промпт в DeepSeek/OpenAI, получая структуру: Заголовок, Тело, Хэштеги (статус `REWRITING`).
6. **Image Generator** синтезирует изображение на основе полученного текста (статус `GENERATING_IMAGE`).
7. Бот переходит в статус `AWAITING_APPROVAL` и присылает готовый черновик с картинкой и кнопками в ЛС автору.
8. Автор нажимает «Опубликовать».
9. Бот публикует фото с подписью в канал, переводит задачу в `PUBLISHED` и редактирует сообщение в ЛС с подтверждением.

### 6.2 Error & Fallback Scenarios
- **Сбой парсинга URL:** Если `trafilatura` не смогла распарсить страницу, используется fallback на `BeautifulSoup`. При невозможности извлечь текст бот возвращает понятную ошибку и предлагает прислать скопированный текст.
- **Сбой основного LLM API (DeepSeek Timeout/500):** Автоматический fallback на резервный провайдер (OpenAI GPT-4o-mini).
- **Сбой Image API:** Бот логирует ошибку, генерирует черновик без изображения (или с плейсхолдером) и сообщает автору: *"Не удалось сгенерировать обложку, пост готов в текстовом формате"*.

---

## 7. Security & Non-Functional Requirements
- **Secrets Management:** Токены `BOT_TOKEN`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `TARGET_CHANNEL_ID` хранятся исключительно в `.env` (не коммитятся в git).
- **Access Control:** Доступ к командам бота и шлюзу одобрения ограничен списком `ALLOWED_USER_IDS`. Любые запросы от посторонних пользователей отклоняются.
- **Sanitization:** Текст экранируется согласно спецификации Telegram MarkdownV2 / HTML во избежание синтаксических ошибок публикации.
- **SQLite Concurrency:** Включение WAL (Write-Ahead Logging) и занятость таймаута для предотвращения `database is locked`.
