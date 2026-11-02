import logging
from typing import List, Optional, Tuple
from src.domain.interfaces import (
    IJobRepository,
    IArticleExtractor,
    ILLMRewriter,
    IImageGenerator,
    IPublisher,
)
from src.domain.models import PublishingJob, Tone, JobStatus, compute_content_hash, ImageAsset

logger = logging.getLogger(__name__)


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

    def _enrich_hashtags(self, draft: PostContent) -> PostContent:
        if not self.channel_hashtags:
            return draft
        combined = list(draft.hashtags)
        seen = {t.lower() for t in combined}
        for tag in self.channel_hashtags:
            if tag.lower() not in seen:
                seen.add(tag.lower())
                combined.append(tag)
        return PostContent(title=draft.title, body=draft.body, hashtags=combined)

    async def submit_content(
        self, user_id: int, source_input: str, tone: Tone = Tone.DYNAMIC
    ) -> Tuple[PublishingJob, bool]:
        """
        Submits content into the system, checks for duplicate by hash.
        Returns: (job, is_duplicate)
        """
        c_hash = compute_content_hash(source_input)
        existing = await self.repository.get_by_hash(c_hash)
        if existing:
            logger.info("Found existing job %s for content hash %s", existing.id, c_hash)
            return existing, True

        job = PublishingJob.create(user_id=user_id, source_input=source_input, tone=tone)
        await self.repository.save(job)
        return job, False

    async def process_pipeline(self, job_id: str) -> PublishingJob:
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
            job.start_extracting()
            await self.repository.save(job)

            if job.is_url:
                title, body = await self.extractor.extract(job.source_input)
            else:
                title = "Пользовательский материал"
                body = job.source_input

            job.set_extracted_content(title=title, body=body)
            await self.repository.save(job)

            # Step 2: LLM Rewriting
            job.status = JobStatus.REWRITING
            await self.repository.save(job)

            if hasattr(self.rewriter, "rewrite_with_prompt"):
                draft, img_prompt = await self.rewriter.rewrite_with_prompt(
                    body, job.tone, title_hint=title
                )
            else:
                draft = await self.rewriter.rewrite(body, job.tone, title_hint=title)
                img_prompt = None

            draft = self._enrich_hashtags(draft)
            job.set_draft(draft)
            await self.repository.save(job)

            # Step 3: Image Generation
            job.status = JobStatus.GENERATING_IMAGE
            await self.repository.save(job)

            prompt_for_image = img_prompt or f"Editorial illustration for news: {draft.title}"
            try:
                image_asset = await self.image_generator.generate(prompt_for_image)
            except Exception as img_err:
                logger.warning("Image generator failed: %s. Using placeholder.", img_err)
                image_asset = ImageAsset(image_url=None, prompt_used=prompt_for_image, is_placeholder=True)

            job.set_image(image_asset)

            # Step 4: Ready for Human Approval
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

    async def regenerate_image(self, job_id: str, custom_prompt: Optional[str] = None) -> PublishingJob:
        """
        Regenerates cover image for an awaiting approval job.
        """
        job = await self.repository.get_by_id(job_id)
        if not job or not job.draft:
            raise ValueError("Invalid job or draft missing")

        prompt = custom_prompt or (job.image.prompt_used if job.image else None) or f"News cover for: {job.draft.title}"
        image_asset = await self.image_generator.generate(prompt)
        job.set_image(image_asset)
        job.status = JobStatus.AWAITING_APPROVAL
        await self.repository.save(job)
        return job

    async def rewrite_text(self, job_id: str, new_tone: Optional[Tone] = None) -> PublishingJob:
        """
        Re-executes LLM rewriting for an awaiting approval job.
        """
        job = await self.repository.get_by_id(job_id)
        if not job:
            raise ValueError("Job not found")

        if new_tone:
            job.tone = new_tone

        body = job.extracted_body or job.source_input
        title_hint = job.extracted_title

        if hasattr(self.rewriter, "rewrite_with_prompt"):
            draft, _ = await self.rewriter.rewrite_with_prompt(body, job.tone, title_hint=title_hint)
        else:
            draft = await self.rewriter.rewrite(body, job.tone, title_hint=title_hint)

        draft = self._enrich_hashtags(draft)
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
