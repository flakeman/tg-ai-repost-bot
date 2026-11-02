from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_approval_keyboard(job_id: str) -> InlineKeyboardMarkup:
    """
    Builds the interactive review keyboard for direct messages.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Опубликовать", callback_data=f"cb:pub:{job_id}"),
            ],
            [
                InlineKeyboardButton(text="🖼️ Перегенерировать фото", callback_data=f"cb:regen_img:{job_id}"),
                InlineKeyboardButton(text="✍️ Переписать текст", callback_data=f"cb:regen_txt:{job_id}"),
            ],
            [
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"cb:reject:{job_id}"),
            ],
        ]
    )


def build_tone_keyboard() -> InlineKeyboardMarkup:
    """
    Builds tone selection keyboard.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔥 Динамичный", callback_data="cb:tone:dynamic"),
                InlineKeyboardButton(text="💼 Экспертный / Формальный", callback_data="cb:tone:formal"),
            ],
            [
                InlineKeyboardButton(text="☕ Разговорный", callback_data="cb:tone:casual"),
                InlineKeyboardButton(text="💡 Аналитический", callback_data="cb:tone:analytical"),
            ],
        ]
    )
