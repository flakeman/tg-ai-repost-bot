# Roadmap: Telegram AI Repost & Publishing Pipeline Bot

## Milestones Overview

### Milestone 1: Core System Architecture, Domain, and Documentation (Current)
- [x] Phase 1.1: Environment, Git initialization, dependencies and configuration
- [ ] Phase 1.2: SDD, DDD, ADRs specifications
- [ ] Phase 1.3: CONTEXT.md and PLAN.md initialization

### Milestone 2: Domain Layer & Repository (TDD)
- [ ] Phase 2.1: Domain Entities (`Article`, `PostDraft`, `PublishingJob`), Value Objects (`URLHash`, `Tone`, `PostStatus`), Domain Events
- [ ] Phase 2.2: Async SQLite Database Schema & Repository (`aiosqlite`) with deduplication checks
- [ ] Phase 2.3: Unit & Integration tests for Domain and Persistence

### Milestone 3: Content Extraction & AI Provider Adapters (TDD)
- [ ] Phase 3.1: Article Extractor (Trafilatura + BeautifulSoup + HTTPX) with title/body parsing and HTML cleanup
- [ ] Phase 3.2: LLM Rewriter Adapter (OpenAI-compatible protocol supporting DeepSeek, GPT-4o-mini, Claude proxy) with fallback and prompt engineering
- [ ] Phase 3.3: Image Generator Adapter (DALL-E 3 / Flux API / Mock provider) with graceful degradation
- [ ] Phase 3.4: Unit & Integration tests with mocked network responses

### Milestone 4: Application Pipeline & Queue Orchestration (TDD)
- [ ] Phase 4.1: Asynchronous Job Queue & Pipeline Orchestrator (`Extract` → `Rewrite` → `Generate Image` → `Awaiting Approval`)
- [ ] Phase 4.2: Error handling, retries, and fallback transitions
- [ ] Phase 4.3: Integration tests for pipeline execution flow

### Milestone 5: Presentation Layer (aiogram 3 Telegram Bot)
- [ ] Phase 5.1: Bot handlers for URL / raw text input and command parsing (`/start`, `/help`, `/rewrite`)
- [ ] Phase 5.2: Interactive Approval Gate in Direct Messages (inline buttons: «Опубликовать», «Перегенерировать фото», «Переписать», «Отклонить»)
- [ ] Phase 5.3: Channel Publisher service (posting photo + markdown caption to target channel)
- [ ] Phase 5.4: End-to-end integration tests

### Milestone 6: Verification, Hardening & Docker Containerization
- [ ] Phase 6.1: Full test suite verification (unit + integration + e2e)
- [ ] Phase 6.2: Dockerfile & docker-compose configuration
- [ ] Phase 6.3: Final audit against AI-RULES and SECURITY-RULES
