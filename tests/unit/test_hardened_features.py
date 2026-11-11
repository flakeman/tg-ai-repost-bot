import os
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.domain.models import JobStatus, PublishingJob, Tone, PostContent, UserSettings
from src.infrastructure.ai.json_parser import RobustJsonParser
from src.infrastructure.storage_manager import StorageManager
from src.application.recovery import recover_orphaned_jobs
from src.application.queue import PipelineQueueWorker
from src.presentation.keyboards import (
    build_settings_main_keyboard,
    build_settings_tone_keyboard,
    build_settings_model_keyboard,
)


def test_robust_json_parser_clean():
    payload = '{"title": "Valid Title", "body": "Clean body", "hashtags": ["#tag1", "#tag2"], "keywords": ["USB key", "AES-256"], "image_prompt": "Clean prompt"}'
    res = RobustJsonParser.parse(payload)
    assert res["title"] == "Valid Title"
    assert res["body"] == "Clean body"
    assert res["hashtags"] == ["#tag1", "#tag2"]
    assert res["keywords"] == ["USB key", "AES-256"]
    assert res["image_prompt"] == "Clean prompt"


def test_robust_json_parser_markdown_and_trailing_commas():
    payload = """```json
    {
        "title": "Markdown Title",
        "body": "Markdown Body text with details.",
        "hashtags": ["#ai", "#python", ],
        "image_prompt": "Futuristic render",
    }
    ```"""
    res = RobustJsonParser.parse(payload)
    assert res["title"] == "Markdown Title"
    assert res["body"] == "Markdown Body text with details."
    assert res["hashtags"] == ["#ai", "#python"]
    assert res["image_prompt"] == "Futuristic render"


def test_robust_json_parser_regex_fallback():
    # Intentionally broken JSON (syntax error with unescaped newline or missing closing bracket)
    broken_payload = 'Here is the response: {"title": "Resilient Title", "body": "Line 1\\nLine 2 without closing braces'
    res = RobustJsonParser.parse(broken_payload)
    assert res["title"] == "Resilient Title"
    assert "Line 1" in res["body"]


def test_robust_json_parser_with_inner_code_blocks():
    # Payload with markdown code block inside "body"
    payload = '''{
        "title": "Ghostty: у ИИ нет прав на PR",
        "body": "**AGENTS.md Ghostty** — инструкция:\\n\\n```\\nzig build\\n-Demit-macos-app=false\\nzig\\n```\\nКонец.",
        "hashtags": ["#ghostty", "#ai"]
    }'''
    res = RobustJsonParser.parse(payload)
    assert res["title"] == "Ghostty: у ИИ нет прав на PR"
    assert "zig build" in res["body"]
    assert "```" in res["body"]
    assert res["hashtags"] == ["#ghostty", "#ai"]


def test_storage_manager_cleanup(tmp_path):
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    # Create old image (15 days old)
    old_file = images_dir / "gen_oldfile1234.png"
    old_file.write_bytes(b"old image bytes")
    past_time = time.time() - (15 * 86400)
    os.utime(str(old_file), (past_time, past_time))

    # Create fresh image
    new_file = images_dir / "gen_freshfile99.png"
    new_file.write_bytes(b"fresh image bytes")

    # Create non-image file
    other_file = images_dir / "notes.txt"
    other_file.write_text("important")

    deleted = StorageManager.cleanup_expired_images(str(images_dir), max_age_days=14)
    assert deleted == 1
    assert not old_file.exists()
    assert new_file.exists()
    assert other_file.exists()

    stats = StorageManager.get_storage_stats(str(images_dir))
    assert stats["file_count"] == 2


@pytest.mark.asyncio
async def test_recover_orphaned_jobs():
    repo_mock = MagicMock()
    bot_mock = MagicMock()
    bot_mock.send_message = AsyncMock()

    stuck_job = PublishingJob.create(user_id=456, source_input="https://example.com/stuck")
    stuck_job.status = JobStatus.EXTRACTING

    repo_mock.get_by_status = AsyncMock(side_effect=lambda status: [stuck_job] if status == JobStatus.EXTRACTING else [])
    repo_mock.save = AsyncMock()

    recovered = await recover_orphaned_jobs(repo_mock, bot=bot_mock)
    assert recovered == 1
    assert stuck_job.status == JobStatus.FAILED
    assert "перезапуском сервера" in stuck_job.error_message
    repo_mock.save.assert_called_once_with(stuck_job)
    bot_mock.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_queue_worker():
    orchestrator_mock = MagicMock()
    bot_mock = MagicMock()
    bot_mock.delete_message = AsyncMock()
    bot_mock.send_photo = AsyncMock()
    bot_mock.send_message = AsyncMock()

    job = PublishingJob.create(user_id=123, source_input="https://example.com/queue")
    job.status = JobStatus.AWAITING_APPROVAL
    job.draft = PostContent(title="Q Title", body="Q Body", hashtags=["#q"])

    orchestrator_mock.process_pipeline = AsyncMock(return_value=job)

    worker = PipelineQueueWorker(orchestrator=orchestrator_mock, bot=bot_mock, max_concurrent=1)
    await worker.start()

    pos = await worker.enqueue(job_id=job.id, chat_id=123, status_message_id=555)
    assert pos >= 1

    # Wait for queue processing
    await worker.queue.join()
    await worker.stop()

    from unittest.mock import ANY
    orchestrator_mock.process_pipeline.assert_called_once_with(job.id, progress_callback=ANY)
    bot_mock.delete_message.assert_called_once_with(chat_id=123, message_id=555)


def test_settings_keyboards():
    kb_main = build_settings_main_keyboard(Tone.DYNAMIC, "gpt-image-2", "@testchannel")
    callbacks = [btn.callback_data for row in kb_main.inline_keyboard for btn in row]
    assert "cb:set:tone_menu" in callbacks
    assert "cb:set:model_menu" in callbacks
    assert "cb:set:cleanup_cache" in callbacks
    assert "cb:set:close" in callbacks

    kb_tones = build_settings_tone_keyboard(Tone.DYNAMIC)
    tone_cbs = [btn.callback_data for row in kb_tones.inline_keyboard for btn in row]
    assert "cb:set:tone:formal" in tone_cbs
    assert "cb:set:main" in tone_cbs

    kb_models = build_settings_model_keyboard("gpt-image-2")
    model_cbs = [btn.callback_data for row in kb_models.inline_keyboard for btn in row]
    assert "cb:set:model:gpt-image-2.5-flare" in model_cbs
    assert "cb:set:main" in model_cbs


def test_remove_pollinations_watermark():
    from PIL import Image, ImageDraw
    import io
    from src.infrastructure.ai.image_generator import remove_pollinations_watermark

    # Create dummy image with watermark in bottom right
    img = Image.new("RGB", (768, 768), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    # Draw fake watermark text/pixels
    draw.rectangle([768 - 150, 768 - 30, 768 - 10, 768 - 10], fill=(255, 255, 255))

    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    orig_bytes = buf.getvalue()

    cleaned_bytes = remove_pollinations_watermark(orig_bytes)
    assert cleaned_bytes is not None

    cleaned_img = Image.open(io.BytesIO(cleaned_bytes))
    assert cleaned_img.size == (768, 768)

    # Check bottom right pixels where watermark was drawn: should no longer be pure white
    corner_pixel = cleaned_img.getpixel((768 - 20, 768 - 20))
    # Original was (255, 255, 255), cleaned should be background (~30, 30, 30)
    assert corner_pixel[0] < 100 and corner_pixel[1] < 100 and corner_pixel[2] < 100


@pytest.mark.asyncio
async def test_pipeline_preserves_substantial_text_with_link():
    from src.application.orchestrator import PipelineOrchestrator
    from src.domain.interfaces import IJobRepository, IArticleExtractor, ILLMRewriter, IImageGenerator, IPublisher
    from src.domain.models import PublishingJob, Tone, PostContent, ImageAsset

    repo_mock = AsyncMock(spec=IJobRepository)
    extractor_mock = AsyncMock(spec=IArticleExtractor)
    # Extractor returns mobile app download boilerplate if called
    extractor_mock.extract_with_url = AsyncMock(return_value=("Qwen", "Official App provided by Qwen Download App Current System does not Support", "https://chat.qwen.ai/"))
    
    rewriter_mock = AsyncMock(spec=ILLMRewriter)
    rewriter_mock.rewrite_with_prompt = AsyncMock(return_value=(
        PostContent(title="Qwen 4 Preview", body="Alibaba released Qwen 4", hashtags=["#AI"]),
        "Illustration of Qwen4 coding AI"
    ))
    
    img_gen_mock = AsyncMock(spec=IImageGenerator)
    img_gen_mock.generate = AsyncMock(return_value=ImageAsset(image_url="storage/images/test.jpg"))
    publisher_mock = AsyncMock(spec=IPublisher)

    orchestrator = PipelineOrchestrator(
        repository=repo_mock,
        extractor=extractor_mock,
        rewriter=rewriter_mock,
        image_generator=img_gen_mock,
        publisher=publisher_mock,
    )

    sample_post = (
        "https://chat.qwen.ai/ Alibaba открыла доступ к Qwen4-Max-Preview, предварительной версии новой модели Qwen 4.\n\n"
        "Попробовать её уже можно в Qwen Chat, режиме Agent Mode и через Alibaba Token Plan.\n\n"
        "Модель предназначена для сложных задач программирования и профессиональной разработки ПО."
    )

    job = PublishingJob.create(user_id=1, source_input=sample_post, tone=Tone.DYNAMIC)
    repo_mock.get_by_id = AsyncMock(return_value=job)
    repo_mock.save = AsyncMock()

    processed = await orchestrator.process_pipeline(job.id)

    # Must preserve the actual post body, NOT replace it with Qwen mobile app download splash!
    assert "Alibaba открыла доступ к Qwen4-Max-Preview" in processed.extracted_body
    assert "Current System does not Support" not in processed.extracted_body
    # Rewriter must have been called with the actual post body
    call_args = rewriter_mock.rewrite_with_prompt.call_args[0]
    assert "Alibaba открыла доступ" in call_args[0]
