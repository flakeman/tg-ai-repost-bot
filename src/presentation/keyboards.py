from typing import Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.domain.models import Tone


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


def build_settings_main_keyboard(current_tone: Tone, current_model: str, channel_id: str) -> InlineKeyboardMarkup:
    tone_labels = {
        Tone.DYNAMIC: "🔥 Динамичный",
        Tone.FORMAL: "💼 Экспертный",
        Tone.CASUAL: "☕ Разговорный",
        Tone.ANALYTICAL: "💡 Аналитический",
        Tone.HUMOROUS: "😄 Ироничный",
    }
    tone_title = tone_labels.get(current_tone, current_tone.value)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"🎭 Стиль рерайта: {tone_title}", callback_data="cb:set:tone_menu"),
            ],
            [
                InlineKeyboardButton(text=f"🎨 Модель картинок: {current_model}", callback_data="cb:set:model_menu"),
            ],
            [
                InlineKeyboardButton(text=f"📢 Канал: {channel_id}", callback_data="cb:set:channel_info"),
            ],
            [
                InlineKeyboardButton(text="🏷️ Хэштеги канала", callback_data="cb:set:hashtags_info"),
                InlineKeyboardButton(text="🧹 Очистить кэш фото", callback_data="cb:set:cleanup_cache"),
            ],
            [
                InlineKeyboardButton(text="✖️ Закрыть настройки", callback_data="cb:set:close"),
            ],
        ]
    )


def build_settings_tone_keyboard(current_tone: Tone) -> InlineKeyboardMarkup:
    tones = [
        (Tone.DYNAMIC, "🔥 Динамичный"),
        (Tone.FORMAL, "💼 Экспертный / Формальный"),
        (Tone.CASUAL, "☕ Разговорный"),
        (Tone.ANALYTICAL, "💡 Аналитический"),
        (Tone.HUMOROUS, "😄 Ироничный / Юмор"),
    ]
    buttons = []
    for tone_enum, label in tones:
        mark = " ✓" if tone_enum == current_tone else ""
        buttons.append([
            InlineKeyboardButton(text=f"{label}{mark}", callback_data=f"cb:set:tone:{tone_enum.value}")
        ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад в настройки", callback_data="cb:set:main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_settings_model_keyboard(current_model: str) -> InlineKeyboardMarkup:
    models = [
        ("gpt-image-2", "gpt-image-2 (Standard)"),
        ("gpt-image-2.5-flare", "gpt-image-2.5-flare (Fast & Resilient)"),
        ("gpt-image-1", "gpt-image-1 (Classic)"),
        ("mock", "Mock (Без реальной генерации)"),
    ]
    buttons = []
    for model_id, label in models:
        mark = " ✓" if model_id == current_model else ""
        buttons.append([
            InlineKeyboardButton(text=f"{label}{mark}", callback_data=f"cb:set:model:{model_id}")
        ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад в настройки", callback_data="cb:set:main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

