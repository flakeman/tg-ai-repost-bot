import pytest
from pydantic import ValidationError
from src.config.settings import Settings


def test_settings_default_values():
    settings = Settings(
        bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        channel_id="@my_test_channel",
        admin_ids=[12345678],
    )
    assert settings.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    assert settings.channel_id == "@my_test_channel"
    assert settings.admin_ids == [12345678]
    assert settings.default_tone == "dynamic"
    assert settings.primary_llm_provider == "deepseek"
    assert settings.fallback_llm_provider == "openai"
    assert settings.db_path == "storage/bot.db"


def test_settings_validation_missing_required():
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_admin_ids_parsing_from_csv():
    settings = Settings(
        bot_token="test_token",
        channel_id="@channel",
        admin_ids="100,200,300",
    )
    assert settings.admin_ids == [100, 200, 300]


def test_settings_channel_hashtags_parsing():
    settings = Settings(
        bot_token="test_token",
        channel_id="https://t.me/etoitnovosti",
        channel_hashtags="#новости, tech, #новости, ai-news",
    )
    assert settings.channel_id == "@etoitnovosti"
    assert settings.channel_hashtags == ["#новости", "#tech", "#ai_news"]
