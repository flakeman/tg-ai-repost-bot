# Project Context: Telegram AI Repost & Publishing Pipeline Bot

## 1. Overview
Проект представляет собой модульный асинхронный конвейер для Telegram-канала:
«Получение источника (URL/текст) → Дедупликация → Извлечение чистого контента → Рерайт через LLM с сохранением фактуры и стиля → Генерация тематической обложки → Предпросмотр с кнопками одобрения/перегенерации в ЛС автора → Публикация в канал».

Версия системы: **1.1.0 (Hardened & Configurable Release)**.

## 2. Tech Stack & Environment
- **Runtime:** Python 3.12 (VPS) / Python 3.14.3 (Local dev)
- **Telegram Framework:** aiogram 3.31.0 (asyncio)
- **Data Validation & Settings:** Pydantic v2 (2.13.5) + Pydantic-Settings
- **Storage:** SQLite via `aiosqlite` (0.22.1) в режиме WAL (`PRAGMA busy_timeout = 5000`)
- **Scraping / Extraction:** `trafilatura` (2.3.1) + `beautifulsoup4` (4.15.0) + `httpx` (0.28.1) + Jina Reader API fallback
- **AI Integration:** OpenAI API SDK (универсальный клиент для DeepSeek Chat/V3, OpenAI GPT-4o-mini, DALL-E 3, Flux API, шлюз cheapvibecode)
- **Testing:** pytest (9.2.0), pytest-asyncio (1.4.1)

## 3. Architecture & Implemented Components
1. `src/domain/`:
   - Модели: `PublishingJob`, `PostContent`, `ImageAsset`, `UserSettings`, `JobStatus`, `Tone`, `compute_content_hash`, `normalize_hashtag`.
   - `UserSettings`: хранение персонального тона рерайта и модели генерации изображений для каждого администратора.
   - Порты интерфейсов: `IJobRepository`, `ISettingsRepository`, `IArticleExtractor`, `ILLMRewriter`, `IImageGenerator`, `IPublisher`.
   - Доменные события: `src/domain/events.py`.
2. `src/infrastructure/`:
   - `database.py`: фабрика соединений `get_db_connection` с принудительным `PRAGMA journal_mode = WAL` и `PRAGMA busy_timeout = 5000`.
   - `repositories.py`:
     - `SqliteJobRepository`: дедупликация по хэшу, устойчивая к конкуренции SQLite.
     - `SqliteSettingsRepository`: персистентность настроек пользователей в таблице `user_settings`.
   - `storage_manager.py`: сервис ротации и очистки дискового кэша (`cleanup_expired_images`, TTL 14 дней).
   - `extractor.py`: `TrafilaturaExtractor` с парсингом Telegram-виджетов, фоллбэком на BeautifulSoup и автоматическим обходом Cloudflare через Jina Reader API (`https://r.jina.ai/<url>`).
   - `ai/json_parser.py`: `RobustJsonParser` с защитой от незакрытых JSON-блоков и markdown-обёрток.
   - `ai/llm_rewriter.py`: интеграция с `RobustJsonParser` и fallback на эвристический парсер.
   - `ai/image_generator.py`: генерация изображений (`gpt-image-2`, DALL-E 3, Flux) с динамическим переопределением модели из настроек пользователя.
3. `src/application/`:
   - `PipelineOrchestrator`: координация этапов пайплайна с учетом пользовательских настроек тона и модели обложек.
   - `queue.py`: `PipelineQueueWorker` — асинхронный воркер на базе `asyncio.Queue` (развязка сетевого поллинга Telegram от тяжелых вызовов LLM/генерации изображений).
   - `recovery.py`: `recover_orphaned_jobs` — стартап-восстановление задач, зависших в статусах `EXTRACTING`, `REWRITING`, `GENERATING_IMAGE` при перезапусках бота.
4. `src/presentation/`:
   - `handlers.py`: хэндлеры команд `/start`, `/help`, `/settings`, `/tone`, приёма ссылок и пересылок, fail-secure авторизация (`is_authorized` отклоняет при пустом списке админов).
   - `keyboards.py`: инлайн-клавиатуры модерации, `/settings` (меню настроек тона, модели генератора, информации о канале и дисковой статистики).
   - `preview.py`: изолированный модуль предпросмотра черновиков (`send_draft_preview`, `get_photo_target`).
   - `publisher.py`: публикация в канал от имени канала единым блоком с фото.
   - `text_utils.py`: безопасное форматирование и чанкинг сообщений.
5. `tests/`:
   - 48 тестов (Unit, Integration, E2E, Hardened Features) — **100% pass rate**.

## 4. Current Status & Deployment
- Развернут на VPS `UPO` (`147.45.124.192`) под управлением PM2 (`id 5: tg-ai-repost-bot`), статус `online`.
- Канал: `@etomoinovosti`. Авторизованный администратор: `422557`.
- Активны все архитектурные решения:
  - `ADR-001` - `ADR-010`: Базовая архитектура, чистая архитектура, DALL-E, aiogram 3.
  - `ADR-011`: Полноценное интерактивное меню настроек `/settings` с персистентностью в SQLite.
  - `ADR-012`: SQLite Concurrency & Busy-timeout Hardening (WAL + 5000ms timeout).
  - `ADR-013`: Асинхронный воркер очередей пайплайна (развязка aiogram и сетевых запросов LLM).
  - `ADR-014`: Стартап-восстановление незавершенных задач и Fail-Secure проверка прав.
  - `ADR-015`: Политика хранения и очистка дискового кэша изображений (TTL 14 дней).
  - `ADR-016`: Устойчивый JSON-парсер и Jina Reader API фоллбэк для защиты от 403 и SPA.
