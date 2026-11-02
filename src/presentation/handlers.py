import logging
from aiogram import Router, F, Bot
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from src.application.orchestrator import PipelineOrchestrator
from src.config.settings import Settings
from src.domain.models import Tone, PublishingJob
from src.presentation.keyboards import build_approval_keyboard, build_tone_keyboard

logger = logging.getLogger(__name__)

router = Router(name="main_router")

# Global session tone memory for the user (in-memory default)
_user_tones: dict[int, Tone] = {}


def is_authorized(user_id: int, settings: Settings) -> bool:
    if not settings.admin_ids:
        return True
    return user_id in settings.admin_ids


async def send_draft_preview(bot: Bot, chat_id: int, job: PublishingJob) -> None:
    """
    Sends interactive preview of the post to the author's direct messages.
    """
    text = job.draft.render_post() if job.draft else "Черновик не сформирован"
    kb = build_approval_keyboard(job.id)

    prefix = "<b>📋 ПРЕДПРОСМОТР ПУБЛИКАЦИИ:</b>\n\n"
    full_text = prefix + text

    if job.image and job.image.image_url and not job.image.is_placeholder:
        if len(full_text) <= 1024:
            await bot.send_photo(
                chat_id=chat_id,
                photo=job.image.image_url,
                caption=full_text,
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
            )
        else:
            await bot.send_photo(
                chat_id=chat_id,
                photo=job.image.image_url,
            )
            await bot.send_message(
                chat_id=chat_id,
                text=full_text,
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
    else:
        note = "\n\n<i>(Изображение отсутствует или используется плейсхолдер)</i>"
        await bot.send_message(
            chat_id=chat_id,
            text=full_text + note,
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
            disable_web_page_preview=True,
        )


@router.message(CommandStart())
async def handle_start(message: Message, settings: Settings):
    if not is_authorized(message.from_user.id, settings):
        await message.answer("⛔ Доступ ограничен. Вы не авторизованы для использования этого бота.")
        return

    welcome_text = (
        "👋 <b>Добро пожаловать в AI News Publisher Bot!</b>\n\n"
        "Этот бот автоматизирует конвейер создания публикаций для вашего канала:\n"
        "1. 📥 Отправьте мне <b>ссылку на статью</b> или <b>скопированный текст</b>.\n"
        "2. 🧠 Нейросеть выделит главное, перепишет текст в динамичном стиле и подберет хэштеги.\n"
        "3. 🎨 Сгенерирует обложку для поста.\n"
        "4. 🔍 Пришлет вам черновик на утверждение перед отправкой в канал.\n\n"
        "Команды:\n"
        "/tone — выбрать стиль изложения\n"
        "/help — подробная справка"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)


@router.message(Command("help"))
async def handle_help(message: Message, settings: Settings):
    if not is_authorized(message.from_user.id, settings):
        return

    help_text = (
        "📖 <b>Справка по использованию:</b>\n\n"
        "• Просто пришлите боту URL (например, <code>https://techcrunch.com/...</code>) "
        "или сырой текст статьи.\n"
        "• Бот проверит материал на дубликаты, чтобы одна и та же новость не вышла дважды.\n"
        "• После генерации вы получите превью с кнопками:\n"
        "  - <b>Опубликовать:</b> отправить в целевой канал.\n"
        "  - <b>Перегенерировать фото:</b> создать новый визуал.\n"
        "  - <b>Переписать текст:</b> запросить другой вариант рерайта.\n"
        "  - <b>Отклонить:</b> отменить пост."
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@router.message(Command("tone"))
async def handle_tone(message: Message, settings: Settings):
    if not is_authorized(message.from_user.id, settings):
        return

    current = _user_tones.get(message.from_user.id, Tone(settings.default_tone))
    await message.answer(
        f"Текущий стиль изложения: <b>{current.value}</b>\nВыберите желаемый тон:",
        reply_markup=build_tone_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data.startswith("cb:tone:"))
async def handle_tone_callback(callback: CallbackQuery):
    tone_str = callback.data.split(":")[2]
    try:
        new_tone = Tone(tone_str)
        _user_tones[callback.from_user.id] = new_tone
        await callback.answer(f"Стиль изменен на: {new_tone.value}")
        await callback.message.edit_text(
            f"✅ Стиль рерайта успешно обновлен на: <b>{new_tone.value}</b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as err:
        await callback.answer("Ошибка выбора тона", show_alert=True)


@router.message(F.text | F.caption)
async def handle_incoming_content(
    message: Message, orchestrator: PipelineOrchestrator, settings: Settings, bot: Bot
):
    user_id = message.from_user.id
    if not is_authorized(user_id, settings):
        await message.answer("⛔ Доступ ограничен.")
        return

    content = (message.text or message.caption or "").strip()
    active_tone = _user_tones.get(user_id, Tone(settings.default_tone))

    # Ingestion & Dedup check
    job, is_duplicate = await orchestrator.submit_content(user_id, content, active_tone)

    if is_duplicate:
        await message.reply(
            f"⚠️ <b>Этот материал уже обрабатывался!</b>\n\n"
            f"ID задачи: <code>{job.id}</code>\n"
            f"Текущий статус: <b>{job.status.value}</b>\n"
            f"Повторная публикация отменена во избежание дубликатов в канале.",
            parse_mode=ParseMode.HTML,
        )
        return

    status_msg = await message.reply(
        "⏳ <b>Принял в работу!</b>\nИзвлекаю контент и запускаю генерацию поста...",
        parse_mode=ParseMode.HTML,
    )

    # Execute pipeline
    processed_job = await orchestrator.process_pipeline(job.id)

    if processed_job.status == PublishingJob.model_fields["status"].default:  # fallback check
        pass

    if processed_job.error_message:
        await status_msg.edit_text(
            f"❌ <b>Произошла ошибка при обработке:</b>\n<code>{processed_job.error_message}</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    await status_msg.delete()
    await send_draft_preview(bot, message.chat.id, processed_job)


@router.callback_query(F.data.startswith("cb:pub:"))
async def handle_publish_callback(
    callback: CallbackQuery, orchestrator: PipelineOrchestrator, settings: Settings
):
    job_id = callback.data.split(":")[2]
    await callback.answer("Публикую в канал...")
    try:
        _, msg_id = await orchestrator.approve_and_publish(job_id, settings.channel_id)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"🚀 <b>Пост успешно опубликован в канале!</b>\nMessage ID: <code>{msg_id}</code>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        logger.error("Publishing callback error: %s", exc)
        await callback.message.answer(f"❌ Ошибка публикации: {exc}")


@router.callback_query(F.data.startswith("cb:regen_img:"))
async def handle_regen_image_callback(
    callback: CallbackQuery, orchestrator: PipelineOrchestrator, bot: Bot
):
    job_id = callback.data.split(":")[2]
    await callback.answer("Перегенерирую обложку...")
    status_msg = await callback.message.answer("🎨 Генерирую новое изображение...")
    try:
        updated_job = await orchestrator.regenerate_image(job_id)
        await status_msg.delete()
        await send_draft_preview(bot, callback.message.chat.id, updated_job)
    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка генерации обложки: {exc}")


@router.callback_query(F.data.startswith("cb:regen_txt:"))
async def handle_regen_text_callback(
    callback: CallbackQuery, orchestrator: PipelineOrchestrator, bot: Bot
):
    job_id = callback.data.split(":")[2]
    await callback.answer("Переписываю текст...")
    status_msg = await callback.message.answer("✍️ Нейросеть готовит новый вариант текста...")
    try:
        updated_job = await orchestrator.rewrite_text(job_id)
        await status_msg.delete()
        await send_draft_preview(bot, callback.message.chat.id, updated_job)
    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка рерайта: {exc}")


@router.callback_query(F.data.startswith("cb:reject:"))
async def handle_reject_callback(callback: CallbackQuery, orchestrator: PipelineOrchestrator):
    job_id = callback.data.split(":")[2]
    await callback.answer("Черновик отклонен.")
    try:
        await orchestrator.reject_job(job_id)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("❌ <b>Черновик отклонен и удален из очереди.</b>", parse_mode=ParseMode.HTML)
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка: {exc}")
