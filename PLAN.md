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
