# Project Context: Telegram AI Repost & Publishing Pipeline Bot

## 1. Overview
Проект представляет собой модульный асинхронный конвейер для Telegram-канала, реализующий цепочку:
«Получение источника (URL/текст) → Дедупликация → Извлечение чистого контента → Рерайт через LLM с сохранением фактуры и стиля → Генерация тематической обложки → Предпросмотр с кнопками одобрения/перегенерации в ЛС автора → Публикация в канал».

## 2. Tech Stack & Environment
- **Runtime:** Python 3.14.3 on Windows
- **Telegram Framework:** aiogram 3 (asyncio)
- **Data Validation & Settings:** Pydantic v2 + Pydantic-Settings
- **Storage:** SQLite via `aiosqlite` (asynchronous, zero-external-dependency, WAL mode)
- **Scraping / Extraction:** `trafilatura` + `beautifulsoup4` + `httpx`
- **AI Integration:** OpenAI API SDK (универсальный клиент для DeepSeek Chat/V3, OpenAI GPT-4o-mini, DALL-E 3, Flux API)
- **Testing:** pytest, pytest-asyncio, pytest-mock, pytest-cov

## 3. Architecture Principles & Layers
Проект организован по принципам Clean Architecture / DDD:
1. `src/domain/`:
   - Сущности (`Article`, `PostDraft`, `PublishingJob`), Value Objects (`URLHash`, `Tone`, `PostStatus`, `ImageSource`), Domain Events (`ArticleReceived`, `ArticleExtracted`, `ContentRewritten`, `ImageGenerated`, `PostApproved`, `PostPublished`, `PostFailed`).
   - Интерфейсы репозиториев и внешних сервисов (Ports).
2. `src/application/`:
   - Сценарии использования (Use Cases) и пайплайн-оркестратор (`PipelineOrchestrator`).
   - Механизм fallback для LLM и деградации генерации картинок.
3. `src/infrastructure/`:
   - Адаптеры внешних систем: `TrafilaturaExtractor`, `OpenAIRewriter`, `DeepSeekRewriter`, `DalleImageGenerator`, `MockImageGenerator`, `SqliteJobRepository`.
4. `src/presentation/`:
   - Роутеры и хэндлеры `aiogram 3`: приём сообщений, инлайн-клавиатуры для модерации, колбэки подтверждения/перегенерации.
5. `src/config/`:
   - Конфигурация через `.env` с валидацией через `BaseSettings`.

## 4. Current Status & Next Steps
- Окружение инициализировано, зависимости устанавливаются.
- Создаются SDD, DDD спецификация и ADR.
- Следующий шаг: реализация доменных сущностей и репозитория с TDD тестами.
