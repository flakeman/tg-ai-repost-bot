import logging
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from src.application.orchestrator import PipelineOrchestrator
from src.application.queue import PipelineQueueWorker
from src.config.settings import Settings
from src.domain.interfaces import ISettingsRepository
from src.domain.models import Tone, PublishingJob, ImageAsset
from src.infrastructure.storage_manager import StorageManager
from src.presentation.preview import get_photo_target, send_draft_preview
from src.presentation.keyboards import (
    build_approval_keyboard,
    build_tone_keyboard,
    build_settings_main_keyboard,
    build_settings_tone_keyboard,
    build_settings_model_keyboard,
)
from src.presentation.text_utils import split_telegram_message, format_progress_message

logger = logging.getLogger(__name__)

router = Router(name="main_router")


def is_authorized(user_id: int, settings: Settings) -> bool:
    if not settings.admin_ids:
        logger.warning("ADMIN_IDS is not configured! Denying access to user %s", user_id)
        return False
    return user_id in settings.admin_ids


@router.message(CommandStart())
async def handle_start(message: Message, settings: Settings):
    if not is_authorized(message.from_user.id, settings):
        await message.answer("⛔ Извините, у вас нет доступа к этому боту.")
        return

    welcome_text = (
        "👋 <b>Добро пожаловать в Telegram AI Repost Bot!</b>\n\n"
        "Я помогу автоматически извлекать статьи и новости по ссылке или тексту, "
        "адаптировать их для Telegram-канала, генерировать обложки и публиковать контент.\n\n"
        "<b>Команды:</b>\n"
        "• /settings — панель настроек (стиль, модель картинок, канал, кэш)\n"
        "• /tone — быстрый выбор тона рерайта\n"
        "• /help — подробная инструкция\n\n"
        "<i>Отправьте мне ссылку на статью или перешлите пост из канала, чтобы начать!</i>"
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
        "  - <b>Отклонить:</b> отменить пост.\n\n"
        "⚙️ Управление параметрами: команда <b>/settings</b>"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@router.message(Command("settings"))
async def handle_settings_command(
    message: Message, settings: Settings, settings_repo: Optional[ISettingsRepository] = None
):
    if not is_authorized(message.from_user.id, settings):
        await message.answer("⛔ Доступ ограничен.")
        return

    user_id = message.from_user.id
    current_tone = Tone(settings.default_tone)
    active_model = settings.dalle_model

    if settings_repo:
        user_settings = await settings_repo.get_user_settings(user_id, default_tone=current_tone)
        current_tone = user_settings.preferred_tone
        active_model = user_settings.preferred_image_model or settings.dalle_model

    hashtags_str = ", ".join(settings.channel_hashtags) if settings.channel_hashtags else "нет"
    text = (
        "⚙️ <b>Панель управления настройками бота</b>\n\n"
        f"• 🎭 <b>Стиль рерайта:</b> <code>{current_tone.value}</code>\n"
        f"• 🎨 <b>Модель генератора обложек:</b> <code>{active_model}</code>\n"
        f"• 📢 <b>Целевой канал:</b> <code>{settings.channel_id}</code>\n"
        f"• 🏷️ <b>Хэштеги канала:</b> <code>{hashtags_str}</code>\n\n"
        "<i>Нажмите на нужный пункт меню для изменения параметров:</i>"
    )
    kb = build_settings_main_keyboard(current_tone, active_model, settings.channel_id)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "cb:set:main")
async def handle_settings_main_callback(
    callback: CallbackQuery, settings: Settings, settings_repo: Optional[ISettingsRepository] = None
):
    user_id = callback.from_user.id
    current_tone = Tone(settings.default_tone)
    active_model = settings.dalle_model

    if settings_repo:
        user_settings = await settings_repo.get_user_settings(user_id, default_tone=current_tone)
        current_tone = user_settings.preferred_tone
        active_model = user_settings.preferred_image_model or settings.dalle_model

    hashtags_str = ", ".join(settings.channel_hashtags) if settings.channel_hashtags else "нет"
    text = (
        "⚙️ <b>Панель управления настройками бота</b>\n\n"
        f"• 🎭 <b>Стиль рерайта:</b> <code>{current_tone.value}</code>\n"
        f"• 🎨 <b>Модель генератора обложек:</b> <code>{active_model}</code>\n"
        f"• 📢 <b>Целевой канал:</b> <code>{settings.channel_id}</code>\n"
        f"• 🏷️ <b>Хэштеги канала:</b> <code>{hashtags_str}</code>\n\n"
        "<i>Нажмите на нужный пункт меню для изменения параметров:</i>"
    )
    kb = build_settings_main_keyboard(current_tone, active_model, settings.channel_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "cb:set:tone_menu")
async def handle_settings_tone_menu(
    callback: CallbackQuery, settings: Settings, settings_repo: Optional[ISettingsRepository] = None
):
    user_id = callback.from_user.id
    current_tone = Tone(settings.default_tone)
    if settings_repo:
        user_settings = await settings_repo.get_user_settings(user_id, default_tone=current_tone)
        current_tone = user_settings.preferred_tone

    text = "🎭 <b>Выберите предпочитаемый стиль (тон) рерайта:</b>"
    kb = build_settings_tone_keyboard(current_tone)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data.startswith("cb:set:tone:"))
async def handle_settings_tone_select(
    callback: CallbackQuery, settings: Settings, settings_repo: Optional[ISettingsRepository] = None
):
    tone_str = callback.data.split(":")[3]
    try:
        new_tone = Tone(tone_str)
        if settings_repo:
            user_settings = await settings_repo.get_user_settings(callback.from_user.id, default_tone=new_tone)
            user_settings.update_tone(new_tone)
            await settings_repo.save_user_settings(user_settings)
        await callback.answer(f"Стиль обновлен: {new_tone.value}")
    except Exception as exc:
        await callback.answer(f"Ошибка выбора стиля: {exc}", show_alert=True)

    # Return to main settings
    await handle_settings_main_callback(callback, settings, settings_repo)


@router.callback_query(F.data == "cb:set:model_menu")
async def handle_settings_model_menu(
    callback: CallbackQuery, settings: Settings, settings_repo: Optional[ISettingsRepository] = None
):
    user_id = callback.from_user.id
    current_model = settings.dalle_model
    if settings_repo:
        user_settings = await settings_repo.get_user_settings(user_id)
        current_model = user_settings.preferred_image_model or settings.dalle_model

    text = "🎨 <b>Выберите модель для генерации обложек:</b>"
    kb = build_settings_model_keyboard(current_model)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data.startswith("cb:set:model:"))
async def handle_settings_model_select(
    callback: CallbackQuery, settings: Settings, settings_repo: Optional[ISettingsRepository] = None
):
    model_str = callback.data.split(":")[3]
    try:
        if settings_repo:
            user_settings = await settings_repo.get_user_settings(callback.from_user.id)
            user_settings.update_image_model(model_str)
            await settings_repo.save_user_settings(user_settings)
        await callback.answer(f"Модель сохранена: {model_str}")
    except Exception as exc:
        await callback.answer(f"Ошибка выбора модели: {exc}", show_alert=True)

    # Return to main settings
    await handle_settings_main_callback(callback, settings, settings_repo)


@router.callback_query(F.data == "cb:set:channel_info")
async def handle_settings_channel_info(callback: CallbackQuery, settings: Settings):
    info_text = (
        f"📢 <b>Информация о канале</b>\n\n"
        f"• Текущий канал: <code>{settings.channel_id}</code>\n"
        f"• Посты публикуются строго от имени этого канала.\n\n"
        f"<i>Для смены канала укажите CHANNEL_ID в конфигурации бота.</i>"
    )
    await callback.answer("Канал: " + settings.channel_id, show_alert=True)


@router.callback_query(F.data == "cb:set:hashtags_info")
async def handle_settings_hashtags_info(callback: CallbackQuery, settings: Settings):
    tags = ", ".join(settings.channel_hashtags) if settings.channel_hashtags else "хэштеги не настроены"
    await callback.answer(f"Постоянные хэштеги:\n{tags}", show_alert=True)


@router.callback_query(F.data == "cb:set:cleanup_cache")
async def handle_settings_cleanup_cache(callback: CallbackQuery):
    deleted = StorageManager.cleanup_expired_images("storage/images", max_age_days=0)
    stats = StorageManager.get_storage_stats("storage/images")
    await callback.answer(
        f"🧹 Очистка завершена!\nУдалено файлов: {deleted}\nОсталось файлов: {stats['file_count']} ({stats['total_size_mb']} МБ)",
        show_alert=True,
    )


@router.callback_query(F.data == "cb:set:close")
async def handle_settings_close(callback: CallbackQuery):
    await callback.answer("Настройки закрыты")
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.message(Command("tone"))
async def handle_tone(message: Message, settings: Settings, settings_repo: Optional[ISettingsRepository] = None):
    if not is_authorized(message.from_user.id, settings):
        return

    current = Tone(settings.default_tone)
    if settings_repo:
        user_settings = await settings_repo.get_user_settings(message.from_user.id, default_tone=current)
        current = user_settings.preferred_tone

    await message.answer(
        f"Текущий стиль изложения: <b>{current.value}</b>\nВыберите желаемый тон:",
        reply_markup=build_tone_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data.startswith("cb:tone:"))
async def handle_tone_callback(
    callback: CallbackQuery, settings: Settings, settings_repo: Optional[ISettingsRepository] = None
):
    tone_str = callback.data.split(":")[2]
    try:
        new_tone = Tone(tone_str)
        if settings_repo:
            user_settings = await settings_repo.get_user_settings(callback.from_user.id, default_tone=new_tone)
            user_settings.update_tone(new_tone)
            await settings_repo.save_user_settings(user_settings)

        await callback.answer(f"Стиль изменен на: {new_tone.value}")
        await callback.message.edit_text(
            f"✅ Стиль рерайта успешно обновлен на: <b>{new_tone.value}</b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as err:
        await callback.answer("Ошибка выбора тона", show_alert=True)


@router.message(F.text | F.caption | F.video | F.photo | F.animation | F.document | F.forward_origin | F.forward_from_chat)
async def handle_incoming_content(
    message: Message,
    orchestrator: PipelineOrchestrator,
    settings: Settings,
    bot: Bot,
    settings_repo: Optional[ISettingsRepository] = None,
    queue_worker: Optional[PipelineQueueWorker] = None,
):
    user_id = message.from_user.id
    logger.info(
        "Incoming content from user %s in chat %s (msg_id: %s, text_len: %d, has_photo: %s, has_forward: %s)",
        user_id,
        message.chat.id,
        message.message_id,
        len(message.text or message.caption or ""),
        bool(message.photo),
        bool(getattr(message, "forward_origin", None) or getattr(message, "forward_from_chat", None)),
    )
    if not is_authorized(user_id, settings):
        await message.answer("⛔ Доступ ограничен.")
        return

    raw_content = (message.text or message.caption or "").strip()
    target_url = None

    # Detect any URLs embedded inside text entities or forwarded channel origin
    entities = (message.entities or []) + (message.caption_entities or [])
    for ent in entities:
        if ent.type == "text_link" and ent.url:
            target_url = ent.url.strip()
            break
        elif ent.type == "url":
            url_part = raw_content[ent.offset : ent.offset + ent.length].strip()
            if url_part:
                target_url = url_part
                break

    if not target_url:
        if getattr(message, "forward_origin", None):
            origin = message.forward_origin
            if getattr(origin, "type", None) == "channel" and getattr(origin, "chat", None):
                chat = origin.chat
                msg_id = getattr(origin, "message_id", None)
                if getattr(chat, "username", None) and msg_id:
                    target_url = f"https://t.me/{chat.username}/{msg_id}"
        elif getattr(message, "forward_from_chat", None):
            chat = message.forward_from_chat
            msg_id = getattr(message, "forward_from_message_id", None)
            if getattr(chat, "username", None) and msg_id:
                target_url = f"https://t.me/{chat.username}/{msg_id}"

    if not raw_content and not target_url:
        await message.reply(
            "⚠️ <b>Не удалось определить текст или ссылку на материал.</b>\n"
            "Пожалуйста, отправьте ссылку на публикацию или перешлите пост из канала.",
            parse_mode=ParseMode.HTML,
        )
        return

    # If URL is the sole content or user forwarded a short post with a URL
    if target_url and (raw_content == target_url or not raw_content or len(raw_content) < 150):
        content = target_url
    elif target_url:
        content = f"{target_url} {raw_content}"
    else:
        content = raw_content

    active_tone = Tone(settings.default_tone)
    if settings_repo:
        user_settings = await settings_repo.get_user_settings(user_id, default_tone=active_tone)
        active_tone = user_settings.preferred_tone

    # Ingestion & Dedup check
    job, is_duplicate = await orchestrator.submit_content(user_id, content, active_tone)

    if not is_duplicate and message.photo:
        largest_photo = message.photo[-1]
        try:
            import os
            os.makedirs("storage/images", exist_ok=True)
            local_photo_path = f"storage/images/fwd_{job.id}.jpg"
            await bot.download(largest_photo.file_id, destination=local_photo_path)
            job.set_image(ImageAsset(image_url=local_photo_path, prompt_used="forwarded telegram media", is_placeholder=False))
            await orchestrator.repository.save(job)
            logger.info("Preserved incoming photo for job %s: %s", job.id, local_photo_path)
        except Exception as photo_err:
            logger.warning("Could not download incoming photo for job %s: %s", job.id, photo_err)

    if is_duplicate:
        if job.status == JobStatus.AWAITING_APPROVAL and job.draft:
            await message.reply(
                "ℹ️ <b>Этот материал уже подготовлен и ожидает вашего решения!</b>\nОтправляю карточку поста повторно:",
                parse_mode=ParseMode.HTML,
            )
            await send_draft_preview(bot, message.chat.id, job)
            return

        await message.reply(
            f"⚠️ <b>Этот материал уже обрабатывался!</b>\n\n"
            f"ID задачи: <code>{job.id}</code>\n"
            f"Текущий статус: <b>{job.status.value}</b>\n"
            f"Повторная публикация отменена во избежание дубликатов в канале.",
            parse_mode=ParseMode.HTML,
        )
        return

    status_msg = await message.reply(
        format_progress_message(5, "Постановка задачи в очередь конвейера..."),
        parse_mode=ParseMode.HTML,
    )

    if queue_worker:
        await queue_worker.enqueue(job.id, message.chat.id, status_msg.message_id)
    else:
        # Direct execution fallback (e.g. in test environments without queue worker)
        async def direct_progress(percent: int, stage_text: str) -> None:
            try:
                await status_msg.edit_text(
                    format_progress_message(percent, stage_text),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

        processed_job = await orchestrator.process_pipeline(job.id, progress_callback=direct_progress)
        if processed_job.error_message:
            await status_msg.edit_text(
                f"❌ <b>Произошла ошибка при обработке:</b>\n<code>{processed_job.error_message}</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        try:
            await status_msg.delete()
        except Exception:
            pass
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
    status_msg = await callback.message.answer(
        format_progress_message(10, "🎨 Подготовка к перегенерации обложки..."),
        parse_mode=ParseMode.HTML,
    )

    async def update_image_progress(percent: int, stage_text: str) -> None:
        try:
            await status_msg.edit_text(
                format_progress_message(percent, stage_text),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    try:
        updated_job = await orchestrator.regenerate_image(
            job_id, progress_callback=update_image_progress
        )
        try:
            await status_msg.delete()
        except Exception:
            pass
        await send_draft_preview(bot, callback.message.chat.id, updated_job)
    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка генерации обложки: {exc}")


@router.callback_query(F.data.startswith("cb:regen_txt:"))
async def handle_regen_text_callback(
    callback: CallbackQuery, orchestrator: PipelineOrchestrator, bot: Bot
):
    job_id = callback.data.split(":")[2]
    await callback.answer("Переписываю текст...")
    status_msg = await callback.message.answer(
        format_progress_message(10, "✍️ Подготовка к повторному рерайту текста..."),
        parse_mode=ParseMode.HTML,
    )

    async def update_text_progress(percent: int, stage_text: str) -> None:
        try:
            await status_msg.edit_text(
                format_progress_message(percent, stage_text),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    try:
        updated_job = await orchestrator.rewrite_text(
            job_id, progress_callback=update_text_progress
        )
        try:
            await status_msg.delete()
        except Exception:
            pass
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
