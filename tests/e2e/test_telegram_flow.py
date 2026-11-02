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
