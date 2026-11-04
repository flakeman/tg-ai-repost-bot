import asyncio
import logging
from typing import Optional, NamedTuple
from aiogram import Bot
from aiogram.enums import ParseMode
from src.application.orchestrator import PipelineOrchestrator
from src.presentation.preview import send_draft_preview

logger = logging.getLogger(__name__)


class QueueItem(NamedTuple):
    job_id: str
    chat_id: int
    status_message_id: Optional[int]


class PipelineQueueWorker:
    def __init__(self, orchestrator: PipelineOrchestrator, bot: Bot, max_concurrent: int = 1):
        self.orchestrator = orchestrator
        self.bot = bot
        self.max_concurrent = max_concurrent
        self.queue: asyncio.Queue[QueueItem] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        for i in range(self.max_concurrent):
            task = asyncio.create_task(self._worker_loop(worker_id=i + 1))
            self._workers.append(task)
        logger.info("PipelineQueueWorker started with %d concurrent worker(s)", self.max_concurrent)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("PipelineQueueWorker stopped")

    async def enqueue(self, job_id: str, chat_id: int, status_message_id: Optional[int] = None) -> int:
        item = QueueItem(job_id=job_id, chat_id=chat_id, status_message_id=status_message_id)
        await self.queue.put(item)
        pos = self.queue.qsize()
        logger.info("Enqueued job %s for chat %s (position in queue: %d)", job_id, chat_id, pos)
        return pos

    async def _worker_loop(self, worker_id: int) -> None:
        logger.debug("Worker #%d started", worker_id)
        while self._running:
            try:
                item = await self.queue.get()
            except asyncio.CancelledError:
                break

            logger.info("Worker #%d processing job %s for chat %s...", worker_id, item.job_id, item.chat_id)
            try:
                processed_job = await self.orchestrator.process_pipeline(item.job_id)

                if processed_job.error_message:
                    if item.status_message_id:
                        try:
                            await self.bot.edit_message_text(
                                chat_id=item.chat_id,
                                message_id=item.status_message_id,
                                text=f"❌ <b>Произошла ошибка при обработке:</b>\n<code>{processed_job.error_message}</code>",
                                parse_mode=ParseMode.HTML,
                            )
                        except Exception as edit_err:
                            logger.warning("Failed to edit error message: %s", edit_err)
                else:
                    # Remove status message
                    if item.status_message_id:
                        try:
                            await self.bot.delete_message(chat_id=item.chat_id, message_id=item.status_message_id)
                        except Exception:
                            pass

                    # Deliver interactive preview
                    await send_draft_preview(self.bot, item.chat_id, processed_job)
                    logger.info("Worker #%d successfully delivered preview for job %s", worker_id, item.job_id)

            except Exception as exc:
                logger.error("Worker #%d unhandled error processing job %s: %s", worker_id, item.job_id, exc, exc_info=True)
                if item.status_message_id:
                    try:
                        await self.bot.edit_message_text(
                            chat_id=item.chat_id,
                            message_id=item.status_message_id,
                            text=f"❌ <b>Непредвиденная ошибка:</b>\n<code>{str(exc)[:200]}</code>",
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass
            finally:
                self.queue.task_done()
