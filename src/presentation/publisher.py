import logging
from typing import Optional
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
from src.domain.interfaces import IPublisher
from src.domain.models import PostContent, ImageAsset
from src.presentation.text_utils import split_telegram_message

logger = logging.getLogger(__name__)


def get_photo_target(image_path_or_url: str):
    if image_path_or_url.startswith("http://") or image_path_or_url.startswith("https://"):
        return image_path_or_url
    return FSInputFile(image_path_or_url)


class TelegramPublisher(IPublisher):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def publish_to_channel(
        self, channel_id: str, draft: PostContent, image: Optional[ImageAsset] = None
    ) -> int:
        post_text = draft.render_post()
        chunks = split_telegram_message(post_text, max_length=4000)

        # Check if valid image URL is available
        if image and image.image_url and not image.is_placeholder:
            photo_target = get_photo_target(image.image_url)
            # Telegram caption limit is 1024 characters
            if len(post_text) <= 1024:
                msg = await self.bot.send_photo(
                    chat_id=channel_id,
                    photo=photo_target,
                    caption=post_text,
                    parse_mode=ParseMode.HTML,
                )
                return msg.message_id
            else:
                # If text exceeds caption length, send photo first, then text chunks
                photo_msg = await self.bot.send_photo(
                    chat_id=channel_id,
                    photo=photo_target,
                )
                first_msg_id = photo_msg.message_id
                for chunk in chunks:
                    await self.bot.send_message(
                        chat_id=channel_id,
                        text=chunk,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
                return first_msg_id

        # Plain text post without image
        first_msg = None
        for chunk in chunks:
            msg = await self.bot.send_message(
                chat_id=channel_id,
                text=chunk,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            if first_msg is None:
                first_msg = msg
        return first_msg.message_id if first_msg else 0
