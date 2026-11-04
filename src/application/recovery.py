from __future__ import annotations
import logging
from typing import Optional
from aiogram import Bot
from aiogram.enums import ParseMode
from src.domain.interfaces import IJobRepository
from src.domain.models import JobStatus

logger = logging.getLogger(__name__)


async def recover_orphaned_jobs(repository: IJobRepository, bot: Optional[Bot] = None) -> int:
    """
    Checks for any jobs stuck in transient/in-progress states (EXTRACTING, REWRITING, GENERATING_IMAGE)
    from previous crashed or restarted process instances. Marks them as FAILED and notifies author.
    Returns: count of recovered orphaned jobs.
    """
    transient_statuses = [
        JobStatus.EXTRACTING,
        JobStatus.REWRITING,
        JobStatus.GENERATING_IMAGE,
    ]

    orphaned_count = 0
    for status in transient_statuses:
        jobs = await repository.get_by_status(status)
        for job in jobs:
            reason = "Процесс обработки был прерван перезапуском сервера или сбоем памяти."
            job.fail(reason)
            await repository.save(job)
            orphaned_count += 1
            logger.warning("Recovered orphaned job %s (was in state %s). Marked as FAILED.", job.id, status.value)

            if bot and job.user_id:
                try:
                    await bot.send_message(
                        chat_id=job.user_id,
                        text=(
                            f"⚠️ <b>Внимание:</b> задача <code>{job.id[:8]}...</code> "
                            f"была прервана перезагрузкой сервиса.\n"
                            f"Вы можете отправить ссылку повторно."
                        ),
                        parse_mode=ParseMode.HTML,
                    )
                except Exception as notify_err:
                    logger.debug("Could not notify user %s of recovered job: %s", job.user_id, notify_err)

    if orphaned_count > 0:
        logger.info("Startup recovery completed: %d orphaned job(s) cleaned up", orphaned_count)
    return orphaned_count
