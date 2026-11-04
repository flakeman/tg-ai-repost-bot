# Master Implementation Plan (PLAN.md)

## Objective
Построить отказоустойчивый модульный Telegram-бот на Python (aiogram 3) с конвейером обработки:
**«Получить контент (URL/текст) → Дедупликация → Извлечь → Переписать через LLM (DeepSeek/OpenAI fallback) → Сгенерировать обложку (DALL-E 3 / Mock) → Отправить черновик автору в ЛС на утверждение → Опубликовать в целевой канал»**.
Разработка ведется строго по правилам `AI-RULES.md`, `SECURITY-RULES.md`, `SDD.md`, `DDD.md` и `ADR`.

---

## 1. Scope & Plan Points

### Point 1: Конфигурация и окружение
- **Files:** `src/config/settings.py`, `.env.example`, `pytest.ini`
- **Logic:** Pydantic-Settings для валидации конфигурации (`BOT_TOKEN`, `CHANNEL_ID`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `ADMIN_IDS`, `DB_PATH`, `DEFAULT_TONE`).
- **Tests:** `tests/unit/test_config.py` (валидация параметров, загрузка переменных окружения).

### Point 2: Доменные сущности, Value Objects и Интерфейсы (DDD)
- **Files:** `src/domain/models.py`, `src/domain/events.py`, `src/domain/interfaces.py`
- **Logic:**
  - Value Objects: `Tone`, `JobStatus`, `ContentHash`, `PostContent`, `ImageAsset`.
  - Aggregate Root: `PublishingJob` с инвариантами переходов статусов.
  - Интерфейсы (Ports): `IJobRepository`, `IArticleExtractor`, `ILLMRewriter`, `IImageGenerator`, `IPublisher`.
- **Tests:** `tests/unit/test_domain_models.py` (проверка инвариантов агрегата, валидация хэшей, переходы состояний).

### Point 3: Инфраструктура хранения и дедупликации (SQLite + aiosqlite)
- **Files:** `src/infrastructure/database.py`, `src/infrastructure/repositories.py`
- **Logic:**
  - Инициализация SQLite базы данных с режимом WAL и таймаутом.
  - Репозиторий `SqliteJobRepository` с методами: `save`, `get_by_id`, `get_by_hash`, `get_by_status`.
  - Дедупликация: проверка наличия хэша перед созданием новой задачи.
- **Tests:** `tests/integration/test_sqlite_repository.py` (CRUD операции, проверка дедупликации, сохранение черновиков и картинок).

### Point 4: Модуль извлечения контента (Article Extractor)
- **Files:** `src/infrastructure/extractor.py`
- **Logic:**
  - `TrafilaturaExtractor`: загрузка веб-страницы через `httpx`, извлечение основного текста и заголовка через `trafilatura`.
  - Fallback на `BeautifulSoup` (парсинг `h1`, `article`, `p`) при нестандартной разметке.
  - Очистка от рекламы, мусорных скриптов и навигационных блоков.
- **Tests:** `tests/unit/test_extractor.py` (тестирование на моковых HTML-страницах, обработка сбоев сети и невалидных URL).

### Point 5: Модули AI (LLM Rewriter + Image Generator + Fallback)
- **Files:** `src/infrastructure/ai/prompts.py`, `src/infrastructure/ai/llm_rewriter.py`, `src/infrastructure/ai/image_generator.py`, `src/infrastructure/ai/composite.py`
- **Logic:**
  - Системный промпт: сохранение ключевых фактов, динамичный слог, структурирование, хэштеги.
  - `OpenAIRewriter` (GPT-4o-mini) и `DeepSeekRewriter` (DeepSeek Chat/V3).
  - `CompositeRewriter` с автоматическим переключением на резервный провайдер при ошибке primary API.
  - `DalleImageGenerator`, `MockImageGenerator` с graceful degradation (пост не ломается при сбое генератора картинок).
- **Tests:** `tests/unit/test_ai_rewriter.py`, `tests/unit/test_image_generator.py` (тестирование парсинга ответов LLM, fallback провайдеров, обработка таймаутов).

### Point 6: Оркестратор конвейера (Application Pipeline)
- **Files:** `src/application/orchestrator.py`, `src/application/use_cases.py`
- **Logic:**
  - Пайплайн: `Ingest` → `Dedup Check` → `Extract` → `Rewrite` → `Generate Image` → `Awaiting Approval`.
  - Обработка действий модератора: `Approve`, `RegenerateImage`, `RewriteText`, `Reject`.
- **Tests:** `tests/integration/test_pipeline_orchestrator.py` (сквозной прогон пайплайна с мок-адаптерами, проверка смены статусов).

### Point 7: Презентационный слой (aiogram 3 Telegram Bot)
- **Files:** `src/presentation/keyboards.py`, `src/presentation/handlers.py`, `src/presentation/publisher.py`, `src/main.py`
- **Logic:**
  - Хэндлеры для `/start`, `/help`, `/rewrite [tone]`, приёма URL и сырого текста.
  - Middleware ограничения доступа по `admin_ids`.
  - Инлайн-клавиатура: «✅ Опубликовать», «🖼️ Перегенерировать фото», «✍️ Переписать текст», «❌ Отклонить».
  - `TelegramPublisher`: отправка фото с форматированной подписью (или чистого текста) в канал.
- **Tests:** `tests/e2e/test_telegram_flow.py` (тестирование обработчиков, симуляция нажатий инлайн-кнопок, проверка вызова публикации).

### Point 8: Контейнеризация и документация
- **Files:** `Dockerfile`, `docker-compose.yml`, `README.md`, `CONTEXT.md` (финальное обновление).
- **Logic:** Легковесный запуск в Docker на любом VPS.
- **Tests:** Полный прогон `pytest` (100% passed).

---

## 2. Phase 2: Systematic Technical Debt Elimination & In-Bot Settings

### Point 9: Архитектурная спецификация (ADR-011 .. ADR-016, SDD, DDD) [DONE]
- **Files:** `docs/adr/ADR-011` .. `ADR-016`, `docs/SDD.md`, `docs/DDD.md`
- **Logic:** Спецификация решений по каждому долгу и интерактивному меню настроек.
- **Tests:** Валидация проектной документации.

### Point 10: Персистентность настроек и интерактивная команда `/settings` (ADR-011) [DONE]
- **Files:** `src/domain/models.py`, `src/infrastructure/database.py`, `src/infrastructure/repositories.py`, `src/presentation/keyboards.py`, `src/presentation/handlers.py`
- **Logic:**
  - Таблица `user_settings` в SQLite (`user_id`, `tone`, `image_model`, `updated_at`).
  - Методы `get_user_settings` и `save_user_settings`.
  - Устранение in-memory `_user_tones` словаря.
  - Команда `/settings` и callback-навигация: переключение тона (`Tone`), выбор модели картинок, инфо о канале и хэштегах.
- **Tests:** Тестирование `user_settings` в unit-тестах репозитория и e2e хэндлеров `/settings`.

### Point 11: Укрепление работы с БД SQLite и фабрика соединений (ADR-012) [DONE]
- **Files:** `src/infrastructure/database.py`, `src/infrastructure/repositories.py`
- **Logic:**
  - Асинхронный контекстный менеджер `get_db_connection(db_path)` с установкой `PRAGMA busy_timeout = 5000` и `PRAGMA journal_mode = WAL` на каждое открываемое соединение.
  - Рефакторинг репозитория на использование фабрики соединений.
- **Tests:** Проверка concurrent read/write тестами в `test_sqlite_repository.py`.

### Point 12: Асинхронная очередь воркера обработки задач (ADR-013) [DONE]
- **Files:** `src/application/queue.py`, `src/presentation/handlers.py`, `src/main.py`
- **Logic:**
  - Реализация `PipelineQueueWorker` на базе `asyncio.Queue`.
  - Хэндлер немедленно отвечает пользователю и кладёт `job_id` в очередь.
  - Воркер выполняет конвейер с контролируемой конкурентностью, обновляет статусное сообщение и присылает превью.
- **Tests:** Тестирование постановки в очередь и обработки через моковый воркер.

### Point 13: Восстановление зависших задач при старте и безопасная авторизация (ADR-014) [DONE]
- **Files:** `src/application/recovery.py`, `src/presentation/handlers.py`, `src/main.py`
- **Logic:**
  - Метод `recover_orphaned_jobs()` при старте приложения: обнаружение задач со статусами `EXTRACTING`, `REWRITING`, `GENERATING_IMAGE`, перевод в `FAILED` с оповещением автора.
  - `is_authorized`: fail-secure режим (если `admin_ids` пуст — доступ запрещен).
- **Tests:** Тестирование логики восстановления задач и авторизации.

### Point 14: Автоматическая очистка и ротация кэша картинок (ADR-015) [DONE]
- **Files:** `src/infrastructure/storage_manager.py`, `src/main.py`
- **Logic:**
  - Модуль `StorageManager.cleanup_expired_images(images_dir, max_age_days=14)`.
  - Периодический фоновый запуск раз в сутки и вызов при старте бота.
- **Tests:** Unit-тест удаления устаревших файлов и сохранения свежих.

### Point 15: Устойчивый парсер JSON и фоллбэк экстрактора Jina Reader (ADR-016) [DONE]
- **Files:** `src/infrastructure/ai/json_parser.py`, `src/infrastructure/ai/llm_rewriter.py`, `src/infrastructure/extractor.py`
- **Logic:**
  - `RobustJsonParser`: безопасный парсинг JSON с очисткой trailing commas и regex-экстракцией полей.
  - `TrafilaturaExtractor`: каскадный фоллбэк на `https://r.jina.ai/<url>` при 403 или блокировках ботов.
- **Tests:** Тесты парсинга невалидного/грязного JSON и извлечения контента.

### Point 16: Полная верификация, деплой на сервер и приёмочное тестирование [DONE]
- **Files:** `tests/*`, развертывание на сервере через PM2.
- **Logic:** Прогон всех тестов (48/48 passed), деплой на `UPO` (`147.45.124.192`), проверка работы `/settings`, recovery и конвейера.
