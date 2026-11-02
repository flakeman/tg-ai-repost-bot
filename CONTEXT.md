# Project Context: Telegram AI Repost & Publishing Pipeline Bot

## 1. Overview
Проект представляет собой модульный асинхронный конвейер для Telegram-канала:
«Получение источника (URL/текст) → Дедупликация → Извлечение чистого контента → Рерайт через LLM с сохранением фактуры и стиля → Генерация тематической обложки → Предпросмотр с кнопками одобрения/перегенерации в ЛС автора → Публикация в канал».

## 2. Tech Stack & Environment
- **Runtime:** Python 3.14.3 on Windows
- **Telegram Framework:** aiogram 3.31.0 (asyncio)
- **Data Validation & Settings:** Pydantic v2 (2.13.5) + Pydantic-Settings
- **Storage:** SQLite via `aiosqlite` (0.22.1) в режиме WAL
- **Scraping / Extraction:** `trafilatura` (2.3.1) + `beautifulsoup4` (4.15.0) + `httpx` (0.28.1)
- **AI Integration:** OpenAI API SDK (универсальный клиент для DeepSeek Chat/V3, OpenAI GPT-4o-mini, DALL-E 3, Flux API)
- **Testing:** pytest (9.2.0), pytest-asyncio (1.4.1)

## 3. Architecture & Implemented Components
1. `src/domain/`:
   - Модели: `PublishingJob`, `PostContent`, `ImageAsset`, `JobStatus`, `Tone`, `compute_content_hash`, `normalize_hashtag`.
   - `PostContent` включает `source_url` (ссылка на первоисточник) и `image_prompts` (4 концепта визуалов).
   - Строгая санитизация `is_valid_url` (защита от переносов строк и ASCII инъекций).
   - Доменные события: `src/domain/events.py`.
   - Порты интерфейсов: `IJobRepository`, `IArticleExtractor`, `ILLMRewriter`, `IImageGenerator`, `IPublisher`.
2. `src/infrastructure/`:
   - `SqliteJobRepository` + `init_db`: персистентность задач и дедупликация по SHA-256 хэшу в режиме WAL.
   - `TrafilaturaExtractor`: парсер статей с поддержкой разворачивания `t.me/<channel>/<id>` через встроенные виджеты (`?embed=1`), парсингом ссылок на первоисточник (Хабр и др.) и фоллбэком на BeautifulSoup.
   - `DeepSeekRewriter`, `OpenAIRewriter`, `CompositeRewriter`: адаптеры LLM с поддержкой кастомных шлюзов (`OPENAI_BASE_URL`), генерации 4 концептов обложек и автоматическим fallback.
   - `DalleImageGenerator`: генерация реальных изображений через `gpt-image-2` / DALL-E, поддержка как прямых URL, так и декодирования `b64_json` с сохранением в `storage/images/`.
3. `src/application/`:
   - `PipelineOrchestrator`: координация шагов конвейера, автоматическое обогащение постоянными хэштегами канала (`channel_hashtags`), сквозная передача `source_url`, дедупликация и модерационные операции (approve, regenerate_image, rewrite_text, reject).
4. `src/presentation/`:
   - `keyboards.py`: инлайн-клавиатуры модерации и выбора тона.
   - `publisher.py`: отправка постов (с фото через `FSInputFile` или только текст) в Telegram-канал с защитой от превышения лимитов Telegram (автоматическое разделение через `split_telegram_message`).
   - `text_utils.py`: безопасное разбиение длинных сообщений по границам параграфов (`\n\n`), строк и пробелов.
   - `handlers.py`: хэндлеры команд `/start`, `/help`, `/tone`, приёма ссылок, пересланных сообщений (`forward_origin`), скрытых ссылок из `message.entities` (`text_link`), превью в ЛС с безопасным чанкингом (кнопки прикрепляются к финальному фрагменту) и интерактивных callback'ов одобрения.
   - `main.py`: точка входа, конфигурация dependency injection, запуск бота с автоматическим удалением старых webhook перед стартом polling.
5. `tests/`:
   - 37 тестов (Unit, Integration, E2E), 100% пройдены.
6. Контейнеризация и процесс-менеджер:
   - `ecosystem.config.js` для PM2, `Dockerfile`, `docker-compose.yml`.

## 4. Current Status
- Развернут на VPS `UPO` (`147.45.124.192`) под управлением PM2 (`tg-ai-repost-bot`).
- Подключен шлюз `https://cheapvibecode.ru/v1` с моделями `gpt-5.6-terra` и `gpt-image-2`.
- Все архитектурные решения зафиксированы в `docs/SDD.md`, `docs/DDD.md` и `docs/adr/ADR-001` - `ADR-009`.
