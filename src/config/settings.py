from typing import Any, List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from src.domain.models import normalize_hashtag


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Bot
    bot_token: str = Field(..., description="Telegram Bot Token from @BotFather")
    channel_id: str = Field(..., description="Telegram Channel ID or username (e.g. @mychannel or -100...)")
    admin_ids: Union[List[int], str] = Field(default_factory=list, description="List of authorized admin user IDs")

    @field_validator("channel_id", mode="before")
    @classmethod
    def normalize_channel_id(cls, v: Any) -> str:
        s = str(v).strip()
        if "t.me/" in s:
            s = s.split("t.me/")[-1].strip("/")
        if not s.startswith("@") and not s.startswith("-"):
            s = f"@{s}"
        return s

    # Storage
    db_path: str = Field(default="storage/bot.db", description="Path to SQLite database file")

    # LLM Settings
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    deepseek_api_key: str = Field(default="", description="DeepSeek API Key")
    primary_llm_provider: str = Field(default="deepseek", description="primary provider: deepseek or openai")
    fallback_llm_provider: str = Field(default="openai", description="fallback provider")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", description="DeepSeek API base URL")
    deepseek_model: str = Field(default="deepseek-chat", description="DeepSeek model name")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model name")

    # Image Generator Settings
    image_provider: str = Field(default="mock", description="image provider: dalle, flux, or mock")
    dalle_model: str = Field(default="dall-e-3", description="DALL-E model name")
    image_style: str = Field(default="modern minimalist, high quality digital editorial illustration", description="Default style prompt modifier")

    # Tone Defaults
    default_tone: str = Field(default="dynamic", description="Default rewriting tone: casual, formal, dynamic")

    # Channel Fixed Hashtags (appended to every post)
    channel_hashtags: Union[List[str], str] = Field(
        default_factory=list,
        description="List of fixed channel hashtags (e.g. #news, #tech)"
    )

    @field_validator("channel_hashtags", mode="before")
    @classmethod
    def parse_channel_hashtags(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            clean = v.strip("[]() ")
            if not clean:
                return []
            items = [item.strip() for item in clean.split(",") if item.strip()]
        elif isinstance(v, (list, tuple)):
            items = list(v)
        else:
            return []

        normalized = []
        seen = set()
        for item in items:
            norm = normalize_hashtag(str(item))
            if norm and norm.lower() not in seen:
                seen.add(norm.lower())
                normalized.append(norm)
        return normalized

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Union[str, List[Union[int, str]], int]) -> List[int]:
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            clean = v.strip("[]() ")
            if not clean:
                return []
            return [int(item.strip()) for item in clean.split(",") if item.strip()]
        if isinstance(v, (list, tuple)):
            return [int(item) for item in v]
        return []
