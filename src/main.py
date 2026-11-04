import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.config.settings import Settings
from src.infrastructure.database import init_db
from src.infrastructure.repositories import SqliteJobRepository, SqliteSettingsRepository
from src.infrastructure.extractor import TrafilaturaExtractor
from src.infrastructure.ai.llm_rewriter import OpenAIRewriter, DeepSeekRewriter
from src.infrastructure.ai.composite import CompositeRewriter
from src.infrastructure.ai.image_generator import DalleImageGenerator, MockImageGenerator
from src.infrastructure.storage_manager import StorageManager
from src.presentation.publisher import TelegramPublisher
from src.application.orchestrator import PipelineOrchestrator
from src.application.queue import PipelineQueueWorker
from src.application.recovery import recover_orphaned_jobs
from src.presentation.handlers import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


def create_bot_app(settings: Settings):
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    return bot, dp


def build_orchestrator(settings: Settings, bot: Bot) -> PipelineOrchestrator:
    # 1. Repository
    repo = SqliteJobRepository(db_path=settings.db_path)

    # 2. Extractor
    extractor = TrafilaturaExtractor()

    # 3. LLM Rewriters & Composite Fallback
    deepseek = DeepSeekRewriter(
        api_key=settings.deepseek_api_key or "unused",
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
    )
    openai_llm = OpenAIRewriter(
        api_key=settings.openai_api_key or "unused",
        model=settings.openai_model,
        base_url=settings.openai_base_url,
    )

    if settings.primary_llm_provider == "deepseek" and settings.deepseek_api_key:
        primary = deepseek
        fallback = openai_llm if settings.openai_api_key else None
    else:
        primary = openai_llm
        fallback = deepseek if settings.deepseek_api_key else None

    composite_rewriter = CompositeRewriter(primary=primary, fallback=fallback)

    # 4. Image Generator
    if settings.image_provider == "dalle" and settings.openai_api_key:
        image_gen = DalleImageGenerator(
            api_key=settings.openai_api_key,
            model=settings.dalle_model,
            style_modifier=settings.image_style,
            client=openai_llm.client,
        )
    else:
        image_gen = MockImageGenerator()

    # 5. Telegram Publisher
    publisher = TelegramPublisher(bot=bot)

    # 6. Orchestrator
    return PipelineOrchestrator(
        repository=repo,
        extractor=extractor,
        rewriter=composite_rewriter,
        image_generator=image_gen,
        publisher=publisher,
        channel_hashtags=settings.channel_hashtags,
    )


async def main():
    settings = Settings()
    if not settings.admin_ids:
        logger.critical("SECURITY WARNING: ADMIN_IDS is empty! Nobody will have access to the bot.")

    logger.info("Initializing database at: %s", settings.db_path)
    await init_db(settings.db_path)

    bot, dp = create_bot_app(settings)
    orchestrator = build_orchestrator(settings, bot)
    settings_repo = SqliteSettingsRepository(db_path=settings.db_path)

    # Startup Maintenance: Recover orphaned jobs & cleanup expired cache
    await recover_orphaned_jobs(repository=orchestrator.repository, bot=bot)
    StorageManager.cleanup_expired_images(images_dir="storage/images", max_age_days=14)

    # Start background queue worker (concurrency = 1)
    queue_worker = PipelineQueueWorker(orchestrator=orchestrator, bot=bot, max_concurrent=1)
    await queue_worker.start()

    # Inject dependencies into aiogram handlers
    dp["settings"] = settings
    dp["orchestrator"] = orchestrator
    dp["settings_repo"] = settings_repo
    dp["queue_worker"] = queue_worker

    logger.info("Starting Telegram Bot long-polling for channel: %s", settings.channel_id)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await queue_worker.stop()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
