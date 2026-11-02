# ADR-006: Support for OpenAI-Compatible Custom Proxy Gateways and Base URL Configuration

## Status
Accepted

## Context
Пользователи часто используют сторонние агрегаторы или OpenAI-совместимые шлюзы (например, `cheapvibecode.ru`, ProxyAPI, VseGPT, OpenRouter) с кастомными ключами (например, с префиксом `sk-cvc-...`) и моделями (`gpt-5.6-terra`, `gemini-3.8-flash`, `gpt-image-2`). По умолчанию официальные SDK направляют запросы на `https://api.openai.com/v1`, что приводит к ошибке `401 Unauthorized / invalid_api_key`.

## Decision
1. Расширить конфигурацию `Settings` (`src/config/settings.py`) параметром `openai_base_url: str = Field(default="https://api.openai.com/v1")`.
2. Передавать `base_url` в конструктор `OpenAIRewriter` и инициализировать `AsyncOpenAI(api_key=..., base_url=...)`.
3. Использовать единый настроенный `client` для LLM-рерайтера и генератора изображений `DalleImageGenerator`.
4. Поддерживать кастомные названия моделей через параметры `OPENAI_MODEL` и `DALLE_MODEL` в `.env`.

## Consequences
- **Плюсы:** Полная совместимость с любым OpenAI-совместимым шлюзом, возможность работы через корпоративные и локальные прокси, гибкая маршрутизация моделей без правки кода.
- **Минусы:** Необходимость проверки корректности передачи `base_url` (обязательное наличие `/v1` в пути у некоторых шлюзов).
