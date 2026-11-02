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
   - Автоматическая нормализация, очистка и дедупликация хэштегов (замена тире на нижние подчеркивания, добавление символа `#`).
   - Доменные события: `src/domain/events.py`.
   - Порты интерфейсов: `IJobRepository`, `IArticleExtractor`, `ILLMRewriter`, `IImageGenerator`, `IPublisher`.
2. `src/infrastructure/`:
   - `SqliteJobRepository` + `init_db`: персистентность задач и дедупликация по SHA-256 хэшу.
   - `TrafilaturaExtractor`: парсер статей с фоллбэком на BeautifulSoup и очисткой мусора.
   - `DeepSeekRewriter`, `OpenAIRewriter`, `CompositeRewriter`: адаптеры LLM с автоматическим резервным переключением (fallback).
   - `DalleImageGenerator`, `MockImageGenerator`: адаптеры генерации обложек с graceful degradation.
3. `src/application/`:
   - `PipelineOrchestrator`: координация шагов конвейера, автоматическое обогащение постоянными хэштегами канала (`channel_hashtags`), дедупликация и модерационные операции (approve, regenerate_image, rewrite_text, reject).
4. `src/presentation/`:
   - `keyboards.py`: инлайн-клавиатуры модерации и выбора тона.
   - `publisher.py`: отправка постов (с фото или только текст) в Telegram-канал.
   - `handlers.py`: хэндлеры команд `/start`, `/help`, `/tone`, приёма ссылок/текста и интерактивных callback'ов одобрения.
   - `main.py`: точка входа, конфигурация dependency injection, запуск бота.
5. `tests/`:
   - 25 тестов (Unit, Integration, E2E), 100% пройдены.
6. Контейнеризация:
   - `Dockerfile`, `docker-compose.yml`.

## 4. Current Status
- Контекст актуален. Проект полностью инициализирован, спроектирован по SDD/DDD/ADR, протестирован и готов к запуску.
