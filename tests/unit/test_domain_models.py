import pytest
from src.domain.models import (
    JobStatus,
    Tone,
    PostContent,
    ImageAsset,
    PublishingJob,
    compute_content_hash,
    normalize_hashtag,
)


def test_normalize_hashtag():
    assert normalize_hashtag("ai-tech") == "#ai_tech"
    assert normalize_hashtag("#CryptoNews") == "#CryptoNews"
    assert normalize_hashtag("  blockchain  ") == "#blockchain"
    assert normalize_hashtag("invalid !@#$ symbols") == "#invalid_symbols"
    assert normalize_hashtag("") == ""


def test_post_content_hashtags_normalization():
    draft = PostContent(
        title="Тест",
        body="Тело поста",
        hashtags=["ai-news", "#AI_News", "Tech", "#Tech", "crypto"],
        keywords="USB security, AES-256, reverse engineering",
    )
    # Checks deduplication case-insensitively and proper leading #
    assert draft.hashtags == ["#ai_news", "#Tech", "#crypto"]
    assert draft.keywords == ["USB security", "AES-256", "reverse engineering"]
    rendered = draft.render_post()
    assert "#ai_news #Tech #crypto" in rendered


def test_compute_content_hash_deterministic():
    text = "   https://Example.COM/news/article-1?utm_source=tg   "
    hash1 = compute_content_hash(text)
    hash2 = compute_content_hash("https://example.com/news/article-1")
    assert hash1 == hash2
    assert len(hash1) == 64


def test_post_content_formatted_text():
    draft = PostContent(
        title="Новый прорыв в ИИ",
        body="Исследователи представили новую модель нейросетей.",
        hashtags=["#AI", "#Tech", "#News"],
        source_url="https://habr.com/ru/articles/123/",
        image_prompts=["🎨 3D-рендер: футуристичная сцена"],
    )
    formatted = draft.render_post()
    assert "<b>Новый прорыв в ИИ</b>" in formatted
    assert "Исследователи представили новую модель" in formatted
    assert 'href="https://habr.com/ru/articles/123/"' in formatted
    assert "#AI #Tech #News" in formatted
    assert draft.image_prompts[0].startswith("🎨")


def test_post_content_render_post_with_max_length():
    huge_body = "Очень важное предложение о технологиях. " * 50  # ~2000 chars
    draft = PostContent(
        title="Заголовок новости",
        body=huge_body,
        hashtags=["#AI", "#Технологии", "#Новости"],
        source_url="https://habr.com/ru/articles/855728/",
    )
    rendered = draft.render_post(max_length=1024)
    assert len(rendered) <= 1024
    assert "<b>Заголовок новости</b>" in rendered
    assert "#AI #Технологии #Новости" in rendered
    assert 'href="https://habr.com/ru/articles/855728/"' in rendered


def test_publishing_job_is_url_sanitization():
    # URL with newlines or spaces must NOT be treated as a pure URL
    job_with_newline = PublishingJob.create(user_id=1, source_input="https://example.com/news\nhttps://example.com/2")
    assert job_with_newline.is_url is False

    job_clean_url = PublishingJob.create(user_id=1, source_input="https://example.com/clean/url")
    assert job_clean_url.is_url is True


def test_publishing_job_lifecycle():
    job = PublishingJob.create(
        user_id=12345,
        source_input="https://example.com/news/1",
        tone=Tone.DYNAMIC,
    )
    assert job.status == JobStatus.PENDING
    assert job.is_url is True

    # Transition to extracting
    job.start_extracting()
    assert job.status == JobStatus.EXTRACTING

    # Extracted content
    job.set_extracted_content(title="Статья", body="Текст статьи...")
    assert job.extracted_title == "Статья"

    # Set draft
    draft = PostContent(title="Рерайт", body="Текст рерайта", hashtags=["#новости"])
    job.set_draft(draft)
    assert job.draft == draft

    # Set image
    job.set_image(ImageAsset(image_url="http://img.png", prompt_used="visual"))
    assert job.image.image_url == "http://img.png"

    # Ready for approval
    job.mark_awaiting_approval()
    assert job.status == JobStatus.AWAITING_APPROVAL

    # Approve & Publish
    job.approve()
    assert job.status == JobStatus.PUBLISHING
    job.mark_published(channel_message_id=999)
    assert job.status == JobStatus.PUBLISHED
    assert job.channel_message_id == 999


def test_cannot_approve_without_draft():
    job = PublishingJob.create(
        user_id=12345,
        source_input="Текст для поста",
        tone=Tone.CASUAL,
    )
    with pytest.raises(ValueError, match="Draft is required"):
        job.mark_awaiting_approval()
