import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import InlineKeyboardMarkup, Message, CallbackQuery, User, Chat
from src.domain.models import PostContent, ImageAsset, PublishingJob, Tone, JobStatus
from src.presentation.keyboards import build_approval_keyboard, build_tone_keyboard
from src.presentation.publisher import TelegramPublisher


def test_approval_keyboard_structure():
    kb = build_approval_keyboard("job-12345")
    assert isinstance(kb, InlineKeyboardMarkup)
    buttons = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("Опубликовать" in b for b in buttons)
    assert any("фото" in b for b in buttons)
    assert any("текст" in b for b in buttons)
    assert any("Отклонить" in b for b in buttons)


def test_tone_keyboard_structure():
    kb = build_tone_keyboard()
    assert isinstance(kb, InlineKeyboardMarkup)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert any("cb:tone:dynamic" in c for c in callbacks)
    assert any("cb:tone:formal" in c for c in callbacks)


@pytest.mark.asyncio
async def test_telegram_publisher_with_photo():
    bot_mock = MagicMock()
    msg_mock = MagicMock()
    msg_mock.message_id = 777
    bot_mock.send_photo = AsyncMock(return_value=msg_mock)

    publisher = TelegramPublisher(bot=bot_mock)
    draft = PostContent(title="Новость", body="Текст новости", hashtags=["#AI"])
    image = ImageAsset(image_url="https://images.com/cover.jpg", is_placeholder=False)

    msg_id = await publisher.publish_to_channel("@test_channel", draft, image)
    assert msg_id == 777
    bot_mock.send_photo.assert_called_once()
    assert bot_mock.send_photo.call_args[1]["chat_id"] == "@test_channel"
    assert "<b>Новость</b>" in bot_mock.send_photo.call_args[1]["caption"]


@pytest.mark.asyncio
async def test_telegram_publisher_without_photo():
    bot_mock = MagicMock()
    msg_mock = MagicMock()
    msg_mock.message_id = 888
    bot_mock.send_message = AsyncMock(return_value=msg_mock)

    publisher = TelegramPublisher(bot=bot_mock)
    draft = PostContent(title="Только текст", body="Текст без фото", hashtags=["#новости"])

    msg_id = await publisher.publish_to_channel("@test_channel", draft, image=None)
    assert msg_id == 888
    bot_mock.send_message.assert_called_once()
    assert "<b>Только текст</b>" in bot_mock.send_message.call_args[1]["text"]


@pytest.mark.asyncio
async def test_telegram_publisher_with_photo_unified_caption():
    bot_mock = MagicMock()
    msg_photo = MagicMock()
    msg_photo.message_id = 901

    bot_mock.send_photo = AsyncMock(return_value=msg_photo)
    bot_mock.send_message = AsyncMock()

    publisher = TelegramPublisher(bot=bot_mock)
    long_body = "Очень длинная новость. " * 250  # ~6000 chars
    draft = PostContent(title="Лонгрид", body=long_body, hashtags=["#длиннопост"])
    image = ImageAsset(image_url="storage/images/test.png", is_placeholder=False)

    msg_id = await publisher.publish_to_channel("@test_channel", draft, image=image)
    assert msg_id == 901
    bot_mock.send_photo.assert_called_once()
    # Post must be in photo caption (unified message)
    caption_sent = bot_mock.send_photo.call_args[1]["caption"]
    assert len(caption_sent) <= 1024
    assert "<b>Лонгрид</b>" in caption_sent
    # No separate message sent
    bot_mock.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_telegram_publisher_plain_text_long_chunking():
    bot_mock = MagicMock()
    msg_chunk = MagicMock()
    msg_chunk.message_id = 902
    bot_mock.send_message = AsyncMock(return_value=msg_chunk)

    publisher = TelegramPublisher(bot=bot_mock)
    long_body = "Текст лонгрида без фото. " * 250  # ~6000 chars
    draft = PostContent(title="Лонгрид", body=long_body, hashtags=["#длиннопост"])

    msg_id = await publisher.publish_to_channel("@test_channel", draft, image=None)
    assert msg_id == 902
    assert bot_mock.send_message.call_count >= 2


@pytest.mark.asyncio
async def test_send_draft_preview_unified_photo_caption_and_keyboard():
    from src.presentation.handlers import send_draft_preview

    bot_mock = MagicMock()
    bot_mock.send_photo = AsyncMock()
    bot_mock.send_message = AsyncMock()

    long_body = "Параграф текста. " * 150
    draft = PostContent(
        title="Единый пост с фото",
        body=long_body,
        hashtags=["#тест"],
        image_prompts=["🎨 Концепт 1", "📊 Концепт 2"]
    )
    job = PublishingJob.create(
        user_id=123,
        source_input="https://example.com/article",
        tone=Tone.DYNAMIC,
    )
    job.draft = draft
    job.image = ImageAsset(image_url="storage/images/test.png", is_placeholder=False)

    await send_draft_preview(bot=bot_mock, chat_id=123, job=job)

    # Photo is sent with post caption and keyboard together in ONE message
    bot_mock.send_photo.assert_called_once()
    photo_call = bot_mock.send_photo.call_args[1]
    assert len(photo_call["caption"]) <= 1024
    assert "<b>Единый пост с фото</b>" in photo_call["caption"]
    assert photo_call["reply_markup"] is not None

    # Secondary message contains only the cover concept suggestions
    bot_mock.send_message.assert_called_once()
    msg_call = bot_mock.send_message.call_args[1]
    assert "Варианты генерации обложки" in msg_call["text"]
    assert msg_call.get("reply_markup") is None
