from __future__ import annotations
import logging
from typing import List, Optional, Tuple, Callable, Awaitable
from src.domain.interfaces import (
    IJobRepository,
    IArticleExtractor,
    ILLMRewriter,
    IImageGenerator,
    IPublisher,
)
from src.domain.models import PublishingJob, Tone, JobStatus, compute_content_hash, ImageAsset, PostContent

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, str], Awaitable[None]]


async def _notify_progress(
    callback: Optional[ProgressCallback], percent: int, stage: str
) -> None:
    if callback:
        try:
            await callback(percent, stage)
        except Exception as exc:
            logger.debug("Progress callback failed (non-fatal): %s", exc)



class PipelineOrchestrator:
    def __init__(
        self,
        repository: IJobRepository,
        extractor: IArticleExtractor,
        rewriter: ILLMRewriter,
        image_generator: IImageGenerator,
        publisher: IPublisher,
        channel_hashtags: Optional[List[str]] = None,
    ):
        self.repository = repository
        self.extractor = extractor
        self.rewriter = rewriter
        self.image_generator = image_generator
        self.publisher = publisher
        self.channel_hashtags = channel_hashtags or []

    def _enrich_hashtags(self, draft: PostContent, source_url: Optional[str] = None) -> PostContent:
        combined = list(draft.hashtags)
        if self.channel_hashtags:
            seen = {t.lower() for t in combined}
            for tag in self.channel_hashtags:
                if tag.lower() not in seen:
                    seen.add(tag.lower())
                    combined.append(tag)
        return PostContent(
            title=draft.title,
            body=draft.body,
            hashtags=combined,
            source_url=source_url or draft.source_url,
            image_prompts=draft.image_prompts,
            keywords=draft.keywords,
        )

    async def submit_content(
        self,
        user_id: int,
        source_input: str,
        tone: Tone = Tone.DYNAMIC,
        source_url: Optional[str] = None,
    ) -> Tuple[PublishingJob, bool]:
        """
        Submits content into the system, checks for duplicate by hash.
        Returns: (job, is_duplicate)
        """
        c_hash = compute_content_hash(source_input)
        existing = await self.repository.get_by_hash(c_hash)
        if existing:
            # If previous job failed or got interrupted/crashed (e.g. still in EXTRACTING or FAILED), allow retrying it
            if existing.status in (JobStatus.EXTRACTING, JobStatus.REWRITING, JobStatus.GENERATING_IMAGE, JobStatus.FAILED):
                logger.info(
                    "Found existing incomplete/failed job %s (status: %s). Resetting to PENDING for retry.",
                    existing.id,
                    existing.status.value,
                )
                existing.status = JobStatus.PENDING
                existing.error_message = None
                existing.tone = tone
                if source_url:
                    existing.source_url = source_url
                await self.repository.save(existing)
                return existing, False
            if source_url and not existing.source_url:
                existing.source_url = source_url
                await self.repository.save(existing)
            logger.info("Found existing job %s for content hash %s", existing.id, c_hash)
            return existing, True

        job = PublishingJob.create(user_id=user_id, source_input=source_input, tone=tone, source_url=source_url)
        await self.repository.save(job)
        return job, False

    async def process_pipeline(
        self,
        job_id: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> PublishingJob:
        """
        Executes the asynchronous pipeline steps:
        1. Extract content (if URL) or prepare raw text.
        2. Rewrite content via LLM.
        3. Generate cover image.
        4. Transition to AWAITING_APPROVAL.
        """
        job = await self.repository.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        try:
            # Step 1: Content Extraction
            await _notify_progress(progress_callback, 15, "📥 Загрузка и извлечение содержимого...")
            job.start_extracting()
            await self.repository.save(job)

            resolved_url = job.source_url
            if job.is_url:
                try:
                    title, body, ext_url = await self.extractor.extract_with_url(job.source_input)
                    resolved_url = ext_url or resolved_url or job.source_input
                except (AttributeError, TypeError):
                    title, body = await self.extractor.extract(job.source_input)
                    resolved_url = resolved_url or job.source_input
            else:
                import re
                text_without_urls = re.sub(r"https?://\S+", "", job.source_input).strip()
                found = re.search(r"https?://\S+", job.source_input)

                if found and not resolved_url:
                    resolved_url = found.group(0).rstrip(".,;!?)")

                # If user already provided substantial text (forwarded post or custom news), use it directly
                if len(text_without_urls) >= 70:
                    lines = [ln.strip() for ln in text_without_urls.split("\n") if ln.strip()]
                    title = lines[0][:80] if lines else "Пользовательский материал"
                    body = job.source_input
                elif found:
                    extracted_target = found.group(0).rstrip(".,;!?)")
                    try:
                        try:
                            title, body, ext_url = await self.extractor.extract_with_url(extracted_target)
                            resolved_url = ext_url or resolved_url
                        except (AttributeError, TypeError):
                            title, body = await self.extractor.extract(extracted_target)

                        # Validate that extracted text is a substantive article, not boilerplate/SPA shell
                        is_boilerplate = any(
                            b_phrase in body.lower()
                            for b_phrase in [
                                "current system does not support",
                                "official app provided by",
                                "download app",
                                "please enable javascript",
                                "enable javascript to continue",
                            ]
                        )
                        if len(body.strip()) < 100 or is_boilerplate:
                            logger.warning("Extracted page appears to be boilerplate/SPA shell, reverting to source text.")
                            title = "Пользовательский материал"
                            body = job.source_input
                    except Exception:
                        title = "Пользовательский материал"
                        body = job.source_input
                else:
                    lines = [ln.strip() for ln in job.source_input.split("\n") if ln.strip()]
                    title = lines[0][:80] if lines else "Пользовательский материал"
                    body = job.source_input

            job.set_extracted_content(title=title, body=body)
            await self.repository.save(job)

            # Step 2: LLM Rewriting
            await _notify_progress(progress_callback, 45, "✍️ Адаптация и рерайт текста нейросетью...")
            job.status = JobStatus.REWRITING
            await self.repository.save(job)

            if hasattr(self.rewriter, "rewrite_with_prompt"):
                draft, img_prompt = await self.rewriter.rewrite_with_prompt(
                    body, job.tone, title_hint=title
                )
            else:
                draft = await self.rewriter.rewrite(body, job.tone, title_hint=title)
                img_prompt = None

            draft = self._enrich_hashtags(draft, source_url=resolved_url or job.source_url)
            job.set_draft(draft)
            await self.repository.save(job)

            # Step 3: Image Generation (Always generate fresh AI artwork, ADR-019)
            await _notify_progress(progress_callback, 75, "🎨 Генерация уникальной ИИ-обложки...")
            job.status = JobStatus.GENERATING_IMAGE
            await self.repository.save(job)

            fallback_existing_image = job.image if (job.image and job.image.image_url and not job.image.is_placeholder) else None
            prompt_for_image = img_prompt or (draft.image_prompts[0] if draft.image_prompts else None) or f"Editorial illustration for news: {draft.title}"

            # Integrate article keys (ADR-020)
            if draft.keywords and not any(k.lower() in prompt_for_image.lower() for k in draft.keywords):
                keys_str = ", ".join(draft.keywords)
                prompt_for_image = f"{prompt_for_image}. Key visual elements: {keys_str}"

            try:
                image_asset = await self.image_generator.generate(prompt_for_image)
            except Exception as img_err:
                logger.warning("Image generator failed: %s", img_err)
                image_asset = fallback_existing_image or ImageAsset(image_url=None, prompt_used=prompt_for_image, is_placeholder=True)

            if image_asset.is_placeholder and fallback_existing_image:
                logger.info("Image generation produced placeholder, falling back to forwarded media.")
                image_asset = fallback_existing_image

            job.set_image(image_asset)

            # Step 4: Ready for Human Approval
            await _notify_progress(progress_callback, 95, "✨ Финализация и подготовка карточки...")
            job.mark_awaiting_approval()
            await self.repository.save(job)
            return job

        except Exception as exc:
            logger.error("Pipeline failed for job %s: %s", job.id, exc, exc_info=True)
            job.fail(str(exc))
            await self.repository.save(job)
            return job

    async def approve_and_publish(self, job_id: str, channel_id: str) -> Tuple[PublishingJob, int]:
        """
        Approves draft and publishes to the designated channel.
        """
        job = await self.repository.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status not in (JobStatus.AWAITING_APPROVAL, JobStatus.PUBLISHING):
            raise ValueError(f"Job {job_id} is in status {job.status}, cannot publish")

        job.approve()
        await self.repository.save(job)

        msg_id = await self.publisher.publish_to_channel(
            channel_id=channel_id,
            draft=job.draft,
            image=job.image,
        )

        job.mark_published(msg_id)
        await self.repository.save(job)
        return job, msg_id

    async def regenerate_image(
        self,
        job_id: str,
        custom_prompt: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> PublishingJob:
        """
        Regenerates cover image for an awaiting approval job.
        Cycles through draft prompts or selects a fresh prompt if none specified (ADR-019).
        """
        job = await self.repository.get_by_id(job_id)
        if not job or not job.draft:
            raise ValueError("Invalid job or draft missing")

        await _notify_progress(progress_callback, 25, "🎨 Анализ концепта и подготовка промпта...")

        if custom_prompt:
            prompt = custom_prompt
        elif job.draft.image_prompts:
            prompts = [p.strip() for p in job.draft.image_prompts if p.strip()]
            current_prompt = job.image.prompt_used if job.image else None
            # If current prompt matches one in list, cycle to next prompt
            if current_prompt in prompts and len(prompts) > 1:
                curr_idx = prompts.index(current_prompt)
                prompt = prompts[(curr_idx + 1) % len(prompts)]
            elif prompts:
                prompt = prompts[0]
            else:
                prompt = f"Editorial illustration for news: {job.draft.title}"
        else:
            prompt = f"Editorial illustration for news: {job.draft.title}"

        # Integrate article keys (ADR-020)
        if job.draft.keywords and not any(k.lower() in prompt.lower() for k in job.draft.keywords):
            keys_str = ", ".join(job.draft.keywords)
            prompt = f"{prompt}. Key visual elements: {keys_str}"

        await _notify_progress(progress_callback, 65, "🖼️ Отрисовка нового нейросетевого арта...")
        image_asset = await self.image_generator.generate(prompt)
        if not image_asset.prompt_used or image_asset.prompt_used == "image prompt":
            image_asset.prompt_used = prompt

        await _notify_progress(progress_callback, 95, "✨ Финализация и сохранение обложки...")
        job.set_image(image_asset)
        job.status = JobStatus.AWAITING_APPROVAL
        await self.repository.save(job)
        return job

    async def rewrite_text(
        self,
        job_id: str,
        new_tone: Optional[Tone] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> PublishingJob:
        """
        Re-executes LLM rewriting for an awaiting approval job.
        """
        job = await self.repository.get_by_id(job_id)
        if not job:
            raise ValueError("Job not found")

        await _notify_progress(progress_callback, 25, "🧠 Анализ статьи и формирование промпта...")

        if new_tone:
            job.tone = new_tone

        body = job.extracted_body or job.source_input
        title_hint = job.extracted_title

        await _notify_progress(progress_callback, 60, "✍️ Генерация нового варианта текста...")
        if hasattr(self.rewriter, "rewrite_with_prompt"):
            draft, _ = await self.rewriter.rewrite_with_prompt(body, job.tone, title_hint=title_hint)
        else:
            draft = await self.rewriter.rewrite(body, job.tone, title_hint=title_hint)

        await _notify_progress(progress_callback, 85, "🏷️ Обогащение хэштегами и форматирование...")
        source_url = job.draft.source_url if (job.draft and job.draft.source_url) else (job.source_input if job.is_url else None)
        draft = self._enrich_hashtags(draft, source_url=source_url)

        await _notify_progress(progress_callback, 95, "✨ Подготовка обновленной карточки...")
        job.set_draft(draft)
        job.status = JobStatus.AWAITING_APPROVAL
        await self.repository.save(job)
        return job

    async def reject_job(self, job_id: str) -> PublishingJob:
        """
        Rejects draft and marks job as cancelled.
        """
        job = await self.repository.get_by_id(job_id)
        if not job:
            raise ValueError("Job not found")

        job.reject()
        await self.repository.save(job)
        return job
