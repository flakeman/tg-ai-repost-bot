import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
from src.domain.models import PublishingJob
from src.presentation.keyboards import build_approval_keyboard
from src.presentation.text_utils import split_telegram_message

logger = logging.getLogger(__name__)


def get_photo_target(image_path_or_url: str):
    if image_path_or_url.startswith("http://") or image_path_or_url.startswith("https://"):
        return image_path_or_url
    return FSInputFile(image_path_or_url)


async def send_draft_preview(bot: Bot, chat_id: int, job: PublishingJob) -> None:
    """
    Sends interactive preview of the post to the author's direct messages.
    If image exists, sends photo with caption and keyboard in ONE single message.
    """
    kb = build_approval_keyboard(job.id)

    if job.image and job.image.image_url and not job.image.is_placeholder:
        photo_target = get_photo_target(job.image.image_url)
        post_caption = job.draft.render_post(max_length=1024) if job.draft else "Черновик не сформирован"

        # Send photo and post text together in ONE message
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo_target,
            caption=post_caption,
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )

        # Send concept suggestions as a supplementary info message
        if job.draft and job.draft.image_prompts:
            prompts_formatted = []
            for p in job.draft.image_prompts:
                clean_p = p.strip()
                if clean_p:
                    prompts_formatted.append(
                        clean_p
                        if clean_p.startswith(("🎨", "📊", "📸", "⚡", "•", "1", "2", "3", "4"))
                        else f"• {clean_p}"
                    )
            if prompts_formatted:
                prompts_text = "<b>🎨 Варианты генерации обложки:</b>\n" + "\n".join(prompts_formatted)
                await bot.send_message(
                    chat_id=chat_id,
                    text=prompts_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
        return

    # Text-only preview (no image)
    text = job.draft.render_post() if job.draft else "Черновик не сформирован"
    full_text = text

    if job.draft and job.draft.image_prompts:
        prompts_formatted = []
        for p in job.draft.image_prompts:
            clean_p = p.strip()
            if clean_p:
                prompts_formatted.append(
                    clean_p
                    if clean_p.startswith(("🎨", "📊", "📸", "⚡", "•", "1", "2", "3", "4"))
                    else f"• {clean_p}"
                )
        if prompts_formatted:
            full_text += "\n\n<b>🎨 Варианты генерации обложки:</b>\n" + "\n".join(prompts_formatted)

    chunks = split_telegram_message(full_text, max_length=4000)
    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        await bot.send_message(
            chat_id=chat_id,
            text=chunk,
            parse_mode=ParseMode.HTML,
            reply_markup=kb if is_last else None,
            disable_web_page_preview=True,
        )
