# 🤖 Telegram AI Repost & Publishing Pipeline Bot

Отказоустойчивый модульный Telegram-бот на базе **Python 3**, **aiogram 3**, **DeepSeek / OpenAI** и **SQLite (WAL)**, реализующий конвейер:
**«Получить контент (URL/текст) → Дедупликация → Извлечь → Переписать через LLM → Сгенерировать обложку → Утвердить в ЛС → Опубликовать в канал»**.

Разработан в строгом соответствии со стандартами **SDD**, **DDD**, **ADR**, **AI-RULES** и **SECURITY-RULES**.

---

## 🚀 Архитектура и возможности

- **Дедупликация контента:** Хэширование нормализованных ссылок и текста (SHA-256). Бот мгновенно предупреждает, если новость уже обрабатывалась.
- **Извлечение контента:** Гибридный экстрактор `trafilatura` + `BeautifulSoup` с автоматической очисткой от рекламных блоков, мусорных тегов и скриптов.
- **Модульный рерайт (LLM):**
  - Поддержка экономичной и быстрой **DeepSeek Chat/V3**.
  - Поддержка **OpenAI GPT-4o-mini**.
  - **Автоматический Fallback:** при сбое или недоступности основного провайдера запрос мгновенно перенаправляется на резервный.
- **Генерация обложек:**
  - Интеграция с **DALL-E 3** и **Flux API**.
  - **Graceful degradation:** при временных сбоях API генерации картинок бот формирует текстовый пост без падения пайплайна.
- **Шлюз утверждения (Human-in-the-Loop):**
  - Никакой автоматической публикации без ведома автора.
  - Интерактивный предпросмотр в ЛС владельца с инлайн-кнопками:
    - 🚀 **Опубликовать** — отправка в канал.
    - 🖼️ **Перегенерировать фото** — создание новой обложки.
    - ✍️ **Переписать текст** — повторный запуск рерайта.
    - ❌ **Отклонить** — отмена публикации.
- **Управление стилем:** Команда `/tone` позволяет на лету менять стиль (`🔥 Динамичный`, `💼 Экспертный`, `☕ Разговорный`, `💡 Аналитический`).
- **Безопасность:**
  - Ограничение доступа по `ADMIN_IDS`.
  - Секреты изолированы в `.env`.

---

## 📁 Структура проекта

```
.
├── .planning/                  # GSD-Codex планирование (PROJECT, ROADMAP, STATE, ISSUES)
├── docs/
│   ├── SDD.md                  # System Design Document
│   ├── DDD.md                  # Domain-Driven Design спецификация
│   └── adr/                    # Архитектурные решения (ADR-001 ... ADR-005)
├── src/
│   ├── domain/                 # Сущности, Value Objects, События, Порты (Interfaces)
│   ├── application/            # Оркестратор конвейера и сценарии использования
│   ├── infrastructure/         # Extractor, SQLite репозиторий, LLM и Image адаптеры
│   ├── presentation/           # aiogram 3 роутеры, хэндлеры, инлайн-клавиатуры
│   ├── config/                 # Pydantic настройки и переменные окружения
│   └── main.py                 # Точка входа в приложение
├── tests/
│   ├── unit/                   # Модульные тесты домена, конфигурации, рерайтера
│   ├── integration/            # Интеграционные тесты SQLite и пайплайна
│   └── e2e/                    # E2E тесты Telegram-потока и публикатора
├── Dockerfile                  # Контейнеризация приложения
├── docker-compose.yml          # Запуск на VPS
├── requirements.txt            # Зависимости
└── README.md
```

---

## 🛠️ Быстрый старт

### 1. Клонирование и настройка окружения
```bash
git clone <repo_url>
cd TG_bot_repost

# Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate  # на Linux / macOS
# или
.\.venv\Scripts\activate   # на Windows

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Конфигурация `.env`
Скопируйте пример конфигурации:
```bash
cp .env.example .env
```
Заполните параметры в `.env`:
```ini
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
CHANNEL_ID=@your_channel_username
ADMIN_IDS=12345678,87654321

DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...

PRIMARY_LLM_PROVIDER=deepseek
FALLBACK_LLM_PROVIDER=openai
IMAGE_PROVIDER=mock  # или dalle
```

### 3. Запуск тестов
```bash
pytest -v
```
Все 25 тестов (Unit, Integration, E2E) выполняются и гарантируют работоспособность конвейера.

### 4. Локальный запуск
```bash
python -m src.main
```

### 5. Запуск в Docker
```bash
docker compose up -d --build
```

---

## 📜 Документация архитектуры
- [System Design Document (SDD)](docs/SDD.md)
- [Domain-Driven Design (DDD)](docs/DDD.md)
- [ADR-001: Асинхронный конвейер](docs/adr/ADR-001-pipeline-architecture.md)
- [ADR-002: aiogram 3](docs/adr/ADR-002-telegram-bot-aiogram3.md)
- [ADR-003: SQLite WAL и дедупликация](docs/adr/ADR-003-storage-and-queue-strategy.md)
- [ADR-004: Универсальные адаптеры ИИ и Fallback](docs/adr/ADR-004-ai-providers-abstraction.md)
- [ADR-005: Шлюз предпросмотра и модерации](docs/adr/ADR-005-preview-and-moderation-gate.md)
