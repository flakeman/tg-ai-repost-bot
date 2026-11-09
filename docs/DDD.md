# Domain-Driven Design (DDD) Specification

## 1. Ubiquitous Language (Единый язык предметной области)
- **Source Material (Исходный материал):** Входящая ссылка (URL) или произвольный текст, передаваемый пользователем боту.
- **Content Hash (Хэш контента):** Детерминированный хэш (SHA-256) нормализованного URL или тела статьи для защиты от повторной обработки (дедупликация).
- **Article (Статья):** Извлеченная и очищенная сущность с заголовком (`title`), основным телом текста (`body`), автором/источником и датой.
- **Tone (Тон рерайта):** Стиль адаптации контента (`formal`, `casual`, `dynamic`, `humorous`, `analytical`).
- **Post Draft (Черновик поста):** Сформированный пост, содержащий заголовок, адаптированный текст, сгенерированные хэштеги и опциональное изображение.
- **Image Asset (Визуальный аспект):** Изображение, сгенерированное по промпту из текста (URL или локальный путь), либо заглушка.
- **Approval Gate (Шлюз утверждения):** Интерактивный этап в ЛС автора с кнопками «Опубликовать», «Переписать текст», «Перегенерировать картинку», «Отклонить».
- **Publishing Job (Задача публикации):** Агрегат конвейера, управляющий жизненным циклом и статусами обработки задачи.
- **Job Status (Статус задачи):** `PENDING` → `EXTRACTING` → `REWRITING` → `GENERATING_IMAGE` → `AWAITING_APPROVAL` → `PUBLISHING` → `PUBLISHED` / `REJECTED` / `FAILED`.

---

## 2. Bounded Contexts (Ограниченные контексты)

```
+-----------------------------------------------------------------------------------+
|                            Ingestion & Dedup Context                              |
|  - Validates input (URL vs raw text)                                              |
|  - Computes ContentHash and queries Repository for duplicates                     |
+-----------------------------------------------------------------------------------+
                                        │
                                        ▼
+-----------------------------------------------------------------------------------+
|                            Extraction Context                                     |
|  - Fetches web page content, cleans boilerplates, extracts title & body           |
+-----------------------------------------------------------------------------------+
                                        │
                                        ▼
+-----------------------------------------------------------------------------------+
|                            Synthesis & AI Context                                 |
|  - Rewriting: Formulates dynamic post with facts & hashtags                       |
|  - Image Generation: Derives visual prompt & generates cover image                |
|  - Fallback logic: Provider switching if primary fails                            |
+-----------------------------------------------------------------------------------+
                                        │
                                        ▼
+-----------------------------------------------------------------------------------+
|                            Moderation & Publishing Context                        |
|  - Previews post in Telegram DM to Channel Owner                                  |
|  - Handles interactive callbacks (Approve, Regenerate Image, Rewrite, Reject)     |
|  - Dispatches final post to target Telegram Channel                               |
+-----------------------------------------------------------------------------------+
```

---

## 3. Aggregates, Entities & Value Objects

### 3.1 Value Objects
- `JobId`: Уникальный идентификатор задачи (UUID4).
- `ContentHash`: SHA-256 хэш нормализованного URL или очищенного текста.
- `Tone`: Enum (`FORMAL`, `CASUAL`, `DYNAMIC`, `HUMOROUS`, `ANALYTICAL`).
- `JobStatus`: Enum состояний конвейера.
- `PostContent`: Неизменяемый объект с полями `title: str`, `body: str`, `hashtags: list[str]`, `source_url: str | None` (ссылка на первоисточник), `image_prompts: list[str]` (варианты промптов/концептов).
- `ImageAsset`: Неизменяемый объект с полями `image_url: str | None` (HTTP-ссылка или локальный путь к файлу), `prompt_used: str | None`, `is_placeholder: bool`.

### 3.2 Aggregate Root: `PublishingJob`
- **ID:** `JobId`
- **Fields:**
  - `user_id: int` (Telegram ID автора)
  - `source_input: str` (исходный URL или текст, очищенный от спецсимволов перевода строк)
  - `is_url: bool` (детерминированная проверка отсутствия пробелов и переводов строк)
  - `content_hash: ContentHash`
  - `tone: Tone`
  - `extracted_title: str | None`
  - `extracted_body: str | None`
  - `draft: PostContent | None`
  - `image: ImageAsset | None`
  - `status: JobStatus`
  - `channel_message_id: int | None`
  - `error_message: str | None`
  - `created_at: datetime`
  - `updated_at: datetime`
- **Invariants:**
  - Нельзя перевести в `AWAITING_APPROVAL` без готового `draft`.
  - Нельзя перевести в `PUBLISHED` без явного вызова метода `approve()`.
  - Если генерация картинки падает с ошибкой, агрегат сохраняет `image = None` и флаг предупреждения, позволяя продолжить публикацию только текста.

### 3.3 Aggregate / Entity: `UserSettings`
- **ID:** `user_id: int` (Telegram ID пользователя/админа)
- **Fields:**
  - `user_id: int`
  - `preferred_tone: Tone` (по умолчанию `Tone.DYNAMIC`)
  - `preferred_image_model: str | None`
  - `updated_at: datetime`
- **Invariants:**
  - `user_id` должен быть положительным числом.
  - Изменение настроек автоматически актуализирует `updated_at`.

---

## 4. Domain Events
- `JobCreatedEvent(job_id, user_id, content_hash)`
- `ArticleExtractedEvent(job_id, title, body_length)`
- `ContentRewrittenEvent(job_id, draft)`
- `ImageGeneratedEvent(job_id, image_url)`
- `AwaitingApprovalEvent(job_id, draft, image)`
- `JobApprovedEvent(job_id, user_id)`
- `JobRegenerateRequestedEvent(job_id, target: "text" | "image")`
- `JobPublishedEvent(job_id, channel_message_id)`
- `JobFailedEvent(job_id, reason)`
- `UserSettingsUpdatedEvent(user_id, tone, image_model)`

---

## 5. Domain Interfaces (Ports)
- `IArticleExtractor`:
  - `async def extract(url: str) -> tuple[str, str]` (title, body)
  - `async def extract_with_url(url: str) -> tuple[str, str, str]` (title, body, final_source_url) — поддерживает разворачивание `t.me/<channel>/<id>` и поиск ссылок на первоисточники (Хабр и др.), фоллбэк на Jina Reader при 403 / защите от ботов.
- `ISettingsRepository`:
  - `async def get_user_settings(user_id: int) -> UserSettings`
  - `async def save_user_settings(settings: UserSettings) -> None`
- `IJobQueue`:
  - `async def enqueue(job_id: str) -> None`
  - `async def dequeue() -> str`
- `IStorageManager`:
  - `def cleanup_expired_images(images_dir: str, max_age_days: int) -> int`
- `ILLMRewriter`:
  - `async def rewrite(raw_text: str, tone: Tone) -> PostContent`
  - `async def rewrite_with_prompt(raw_text: str, tone: Tone, title_hint: str | None) -> tuple[PostContent, str | None]`
- `IImageGenerator`: `async def generate(prompt: str) -> ImageAsset` (поддерживает DALL-E/OpenAI, автономный резервный провайдер Pollinations AI и композитную маршрутизацию `CompositeImageGenerator` с автоматическим fallback при ошибках 403 / model_not_allowed)
- `IJobRepository`:
  - `async def save(job: PublishingJob) -> None`
  - `async def get_by_id(job_id: str) -> PublishingJob | None`
  - `async def get_by_hash(content_hash: str) -> PublishingJob | None`
  - `async def get_pending_jobs() -> list[PublishingJob]`
- `IPublisher`: `async def publish_to_channel(channel_id: str, draft: PostContent, image: ImageAsset | None) -> int` (поддерживает `FSInputFile` для локальных файлов и URL для удаленных, с отправкой единого сообщения «фото + подпись» до 1024 символов)
- `split_telegram_message`: Presentation helper для деления текста на сообщения до 4000 символов по границам параграфов (для текстовых постов).

---

## 6. Resilience & State Invariants (ADR-017)
- **Retry Invariant for Failed Jobs:** Если агрегат `PublishingJob` находился в терминальном статусе `FAILED` или промежуточных незавершённых статусах (`EXTRACTING`, `REWRITING`, `GENERATING_IMAGE`), повторный вызов метода `submit_content` сбрасывает статус агрегата в `PENDING`, очищает `error_message = None`, обновляет `tone` и `updated_at`, переводя задачу на повторную обработку (`is_duplicate = False`).
- **Forwarded Media Invariant:** При поступлении пересланного сообщения с медиа (`photo`), исходное изображение сохраняется локально как `ImageAsset` и привязывается к задаче до этапа генерации, исключая потерю оригинальных иллюстраций.
- **Unified Single-Bubble Presentation:** Все публикации с изображением оформляются строго единым сообщением `send_photo` с подписью до 1024 символов как в ЛС модератора, так и в целевом канале.
- **Autonomous Image Fallback Invariant (ADR-018):** Если основной шлюз генерации изображений возвращает ошибку отсутствия прав или неподдерживаемой модели (HTTP 403 `model_not_allowed`), композитный генератор автоматически перенаправляет запрос на независимый провайдер `PollinationsImageGenerator`, гарантируя наличие обложки у каждого поста.
