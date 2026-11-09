import pytest
from unittest.mock import AsyncMock, MagicMock
from src.domain.models import Tone, JobStatus, PostContent, ImageAsset
from src.infrastructure.database import init_db
from src.infrastructure.repositories import SqliteJobRepository
from src.application.orchestrator import PipelineOrchestrator


@pytest.fixture
async def setup_pipeline(tmp_path):
    db_file = str(tmp_path / "test_pipeline.db")
    await init_db(db_file)
    repo = SqliteJobRepository(db_file)

    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=("Original Title", "Original Body of the news article."))

    rewriter = MagicMock()
    draft = PostContent(title="Dynamic Title", body="Rewritten Body", hashtags=["#news"])
    rewriter.rewrite_with_prompt = AsyncMock(return_value=(draft, "image prompt for visual"))

    image_gen = MagicMock()
    image_gen.generate = AsyncMock(side_effect=lambda p: ImageAsset(image_url="http://img.com/1.png", prompt_used=p))

    publisher = MagicMock()
    publisher.publish_to_channel = AsyncMock(return_value=12345)

    orchestrator = PipelineOrchestrator(
        repository=repo,
        extractor=extractor,
        rewriter=rewriter,
        image_generator=image_gen,
        publisher=publisher,
    )

    return orchestrator, repo, publisher


@pytest.mark.asyncio
async def test_submit_new_and_duplicate_content(setup_pipeline):
    orchestrator, repo, _ = setup_pipeline

    job1, is_dup1 = await orchestrator.submit_content(
        user_id=1,
        source_input="https://tech.com/news/1",
        tone=Tone.DYNAMIC,
    )
    assert is_dup1 is False
    assert job1.status == JobStatus.PENDING

    # Second submission with same URL (even with query param) should be detected as duplicate
    job2, is_dup2 = await orchestrator.submit_content(
        user_id=1,
        source_input="https://tech.com/news/1?utm_medium=tg",
        tone=Tone.DYNAMIC,
    )
    assert is_dup2 is True
    assert job2.id == job1.id


@pytest.mark.asyncio
async def test_full_pipeline_process_to_approval(setup_pipeline):
    orchestrator, repo, _ = setup_pipeline

    job, _ = await orchestrator.submit_content(
        user_id=1,
        source_input="https://tech.com/news/feature",
        tone=Tone.DYNAMIC,
    )

    processed_job = await orchestrator.process_pipeline(job.id)

    assert processed_job.status == JobStatus.AWAITING_APPROVAL
    assert processed_job.extracted_title == "Original Title"
    assert processed_job.draft is not None
    assert processed_job.draft.title == "Dynamic Title"
    assert processed_job.image is not None
    assert processed_job.image.image_url == "http://img.com/1.png"


@pytest.mark.asyncio
async def test_approve_and_publish_flow(setup_pipeline):
    orchestrator, repo, publisher = setup_pipeline

    job, _ = await orchestrator.submit_content(
        user_id=1,
        source_input="Breaking news raw text about AI advancements",
        tone=Tone.DYNAMIC,
    )
    await orchestrator.process_pipeline(job.id)

    published_job, msg_id = await orchestrator.approve_and_publish(job.id, channel_id="@my_channel")

    assert published_job.status == JobStatus.PUBLISHED
    assert published_job.channel_message_id == 12345
    assert msg_id == 12345
    publisher.publish_to_channel.assert_called_once()


@pytest.mark.asyncio
async def test_reject_job_flow(setup_pipeline):
    orchestrator, repo, _ = setup_pipeline

    job, _ = await orchestrator.submit_content(user_id=1, source_input="Test content")
    await orchestrator.process_pipeline(job.id)

    rejected_job = await orchestrator.reject_job(job.id)
    assert rejected_job.status == JobStatus.REJECTED


@pytest.mark.asyncio
async def test_retry_failed_job_resets_status(setup_pipeline):
    orchestrator, repo, _ = setup_pipeline

    job, is_dup = await orchestrator.submit_content(user_id=1, source_input="Content that will fail")
    assert is_dup is False

    # Simulate job failure (e.g. LLM quota error)
    job.fail("Error 402: Quota exceeded")
    await repo.save(job)
    assert job.status == JobStatus.FAILED
    assert job.error_message == "Error 402: Quota exceeded"

    # Resubmitting the same content should allow retry, resetting to PENDING
    retry_job, is_dup_retry = await orchestrator.submit_content(
        user_id=1, source_input="Content that will fail", tone=Tone.FORMAL
    )
    assert is_dup_retry is False
    assert retry_job.id == job.id
    assert retry_job.status == JobStatus.PENDING
    assert retry_job.error_message is None
    assert retry_job.tone == Tone.FORMAL


@pytest.mark.asyncio
async def test_process_pipeline_generates_fresh_ai_image_and_uses_forwarded_as_fallback(setup_pipeline):
    orchestrator, repo, _ = setup_pipeline

    job, _ = await orchestrator.submit_content(user_id=1, source_input="https://tech.com/news/with_photo")
    # Attach a forwarded image beforehand
    job.set_image(ImageAsset(image_url="storage/images/fwd_test.jpg", is_placeholder=False))
    await repo.save(job)

    # 1. Image generator succeeds -> produces fresh AI artwork (ADR-019)
    processed_job = await orchestrator.process_pipeline(job.id)
    assert processed_job.status == JobStatus.AWAITING_APPROVAL
    assert processed_job.image.image_url == "http://img.com/1.png"
    assert not processed_job.image.is_placeholder

    # 2. When generator produces placeholder or fails -> falls back to forwarded image
    class FailingGenerator:
        async def generate(self, prompt: str):
            return ImageAsset(image_url=None, prompt_used=prompt, is_placeholder=True)

    orchestrator.image_generator = FailingGenerator()
    job2, _ = await orchestrator.submit_content(user_id=1, source_input="https://tech.com/news/with_photo_fallback")
    job2.set_image(ImageAsset(image_url="storage/images/fwd_test2.jpg", is_placeholder=False))
    await repo.save(job2)

    processed_job2 = await orchestrator.process_pipeline(job2.id)
    assert processed_job2.status == JobStatus.AWAITING_APPROVAL
    assert processed_job2.image.image_url == "storage/images/fwd_test2.jpg"


@pytest.mark.asyncio
async def test_regenerate_image_cycles_prompts(setup_pipeline):
    orchestrator, repo, _ = setup_pipeline
    job, _ = await orchestrator.submit_content(user_id=1, source_input="https://tech.com/news/regen")
    job = await orchestrator.process_pipeline(job.id)

    # Ensure draft has multiple prompts
    job.draft.image_prompts = ["Concept 1: Isometric 3D", "Concept 2: Cyberpunk neon", "Concept 3: Minimalist vector"]
    job.image.prompt_used = "Concept 1: Isometric 3D"
    await repo.save(job)

    # Calling regenerate_image without custom prompt should cycle to Concept 2
    regen_job = await orchestrator.regenerate_image(job.id)
    assert regen_job.image.prompt_used == "Concept 2: Cyberpunk neon"

