import os
import pytest
from src.domain.models import PublishingJob, Tone, JobStatus, PostContent, ImageAsset
from src.infrastructure.database import init_db
from src.infrastructure.repositories import SqliteJobRepository


@pytest.fixture
async def temp_repo(tmp_path):
    db_file = str(tmp_path / "test_jobs.db")
    await init_db(db_file)
    return SqliteJobRepository(db_file)


@pytest.mark.asyncio
async def test_save_and_retrieve_job_by_id(temp_repo):
    job = PublishingJob.create(
        user_id=123,
        source_input="https://techcrunch.com/article-1",
        tone=Tone.DYNAMIC,
    )
    job.start_extracting()
    job.set_extracted_content(title="Test Title", body="Original body text")
    draft = PostContent(title="Rewritten Title", body="Rewritten body", hashtags=["#ai", "#news"])
    job.set_draft(draft)
    image = ImageAsset(image_url="https://images.com/pic1.jpg", prompt_used="futuristic ai robot")
    job.set_image(image)
    job.mark_awaiting_approval()

    await temp_repo.save(job)

    retrieved = await temp_repo.get_by_id(job.id)
    assert retrieved is not None
    assert retrieved.id == job.id
    assert retrieved.user_id == 123
    assert retrieved.content_hash == job.content_hash
    assert retrieved.status == JobStatus.AWAITING_APPROVAL
    assert retrieved.extracted_title == "Test Title"
    assert retrieved.draft is not None
    assert retrieved.draft.title == "Rewritten Title"
    assert retrieved.draft.hashtags == ["#ai", "#news"]
    assert retrieved.image is not None
    assert retrieved.image.image_url == "https://images.com/pic1.jpg"


@pytest.mark.asyncio
async def test_deduplication_via_get_by_hash(temp_repo):
    job = PublishingJob.create(
        user_id=123,
        source_input="https://example.com/breaking-news",
        tone=Tone.FORMAL,
    )
    await temp_repo.save(job)

    # Attempt to find by content hash of normalized url
    same_job = await temp_repo.get_by_hash(job.content_hash)
    assert same_job is not None
    assert same_job.id == job.id


@pytest.mark.asyncio
async def test_get_by_status(temp_repo):
    job1 = PublishingJob.create(user_id=1, source_input="text 1")
    job2 = PublishingJob.create(user_id=2, source_input="text 2")
    job1.fail("Network error")

    await temp_repo.save(job1)
    await temp_repo.save(job2)

    failed_jobs = await temp_repo.get_by_status(JobStatus.FAILED)
    pending_jobs = await temp_repo.get_by_status(JobStatus.PENDING)

    assert len(failed_jobs) == 1
    assert failed_jobs[0].id == job1.id
    assert len(pending_jobs) == 1
    assert pending_jobs[0].id == job2.id


@pytest.mark.asyncio
async def test_source_url_persistence(temp_repo):
    job = PublishingJob.create(
        user_id=123,
        source_input="https://habr.com/ru/articles/1102922/",
        tone=Tone.DYNAMIC,
    )
    draft = PostContent(
        title="Заголовок",
        body="Текст",
        hashtags=["#tag"],
        source_url="https://habr.com/ru/articles/1102922/",
    )
    job.set_draft(draft)
    await temp_repo.save(job)

    loaded = await temp_repo.get_by_id(job.id)
    assert loaded is not None
    assert loaded.draft is not None
    assert loaded.draft.source_url == "https://habr.com/ru/articles/1102922/"


@pytest.mark.asyncio
async def test_user_settings_persistence(tmp_path):
    from src.domain.models import UserSettings
    from src.infrastructure.repositories import SqliteSettingsRepository

    db_file = str(tmp_path / "test_settings.db")
    await init_db(db_file)
    settings_repo = SqliteSettingsRepository(db_file)

    # Initial default retrieval
    settings = await settings_repo.get_user_settings(999, default_tone=Tone.ANALYTICAL)
    assert settings.user_id == 999
    assert settings.preferred_tone == Tone.ANALYTICAL
    assert settings.preferred_image_model is None

    # Update and save
    settings.update_tone(Tone.HUMOROUS)
    settings.update_image_model("gpt-image-2.5-flare")
    await settings_repo.save_user_settings(settings)

    # Re-read
    loaded = await settings_repo.get_user_settings(999)
    assert loaded.user_id == 999
    assert loaded.preferred_tone == Tone.HUMOROUS
    assert loaded.preferred_image_model == "gpt-image-2.5-flare"

