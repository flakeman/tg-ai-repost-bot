from __future__ import annotations
import hashlib
import html
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from urllib.parse import urlparse, urlunparse
from pydantic import BaseModel, Field, field_validator


class JobStatus(str, Enum):
    PENDING = "PENDING"
    EXTRACTING = "EXTRACTING"
    REWRITING = "REWRITING"
    GENERATING_IMAGE = "GENERATING_IMAGE"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class Tone(str, Enum):
    CASUAL = "casual"
    FORMAL = "formal"
    DYNAMIC = "dynamic"
    HUMOROUS = "humorous"
    ANALYTICAL = "analytical"


def normalize_hashtag(tag: str) -> str:
    """
    Normalizes a hashtag:
    - strips spaces and leading '#'
    - replaces hyphens and whitespace with underscores
    - removes non-alphanumeric characters (keeping underscore)
    - returns with leading '#'
    """
    cleaned = tag.strip().lstrip("#").replace("-", "_")
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"[^\w]", "", cleaned)
    cleaned = re.sub(r"_{2,}", "_", cleaned).strip("_")
    return f"#{cleaned}" if cleaned else ""


def compute_content_hash(content: str) -> str:
    """
    Computes a deterministic SHA-256 hash.
    If the content is a URL, normalizes it by removing UTM parameters, fragments,
    and trailing slashes. If raw text, normalizes whitespace.
    """
    stripped = content.strip()
    if stripped.startswith("http://") or stripped.startswith("https://"):
        parsed = urlparse(stripped)
        # Drop UTM queries
        query_parts = []
        if parsed.query:
            for pair in parsed.query.split("&"):
                if not pair.lower().startswith("utm_") and not pair.lower().startswith("fbclid"):
                    query_parts.append(pair)
        normalized_query = "&".join(sorted(query_parts))
        normalized_path = parsed.path.rstrip("/")
        normalized_url = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            normalized_path,
            "",
            normalized_query,
            "",
        ))
        raw = normalized_url
    else:
        # Normalize whitespace in raw text
        raw = re.sub(r"\s+", " ", stripped).lower()

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class PostContent(BaseModel):
    title: str
    body: str
    hashtags: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    image_prompts: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)

    @field_validator("keywords", mode="before")
    @classmethod
    def clean_keywords(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v = [k.strip() for k in v.split(",") if k.strip()]
        if not isinstance(v, (list, tuple)):
            return []
        return [str(k).strip() for k in v if str(k).strip()]

    @field_validator("hashtags", mode="before")
    @classmethod
    def clean_and_normalize_hashtags(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v = [t.strip() for t in v.replace(",", " ").split() if t.strip()]
        if not isinstance(v, (list, tuple)):
            return []
        result = []
        seen = set()
        for item in v:
            norm = normalize_hashtag(str(item))
            if norm and norm.lower() not in seen:
                seen.add(norm.lower())
                result.append(norm)
        return result

    def render_post(self, max_length: Optional[int] = None) -> str:
        """
        Renders ready-to-publish Telegram HTML format.
        If max_length is specified (e.g. 1024 for photo caption),
        safely constrains the total length within the limit.
        Automatically converts markdown code formatting (`code`, ```blocks```) to Telegram HTML.
        """
        from src.presentation.text_utils import convert_markdown_to_telegram_html

        clean_title = html.escape(self.title.strip().replace("**", "").replace("<b>", "").replace("</b>", ""))
        header = f"<b>{clean_title}</b>"
        source_part = f'<a href="{self.source_url}">🔗 Источник</a>' if self.source_url else ""
        raw_body = convert_markdown_to_telegram_html(self.body.strip())
        body_text = raw_body

        if max_length:
            footer_parts = []
            if source_part:
                footer_parts.extend(["", source_part])
            if tags_str := " ".join(self.hashtags) if self.hashtags else "":
                footer_parts.extend(["", tags_str])
            footer_text = "\n".join(footer_parts)

            # overhead: header + newline + footer
            overhead = len(header) + 1 + len(footer_text)
            if overhead + len(body_text) > max_length:
                max_body = max_length - overhead - 4
                if max_body > 50:
                    truncated = body_text[:max_body]
                    last_punct = max(
                        truncated.rfind(". "),
                        truncated.rfind("! "),
                        truncated.rfind("? "),
                        truncated.rfind("\n"),
                    )
                    if last_punct > max_body // 2:
                        body_text = truncated[:last_punct + 1]
                    else:
                        last_space = truncated.rfind(" ")
                        if last_space > max_body // 2:
                            body_text = truncated[:last_space] + "..."
                        else:
                            body_text = truncated + "..."
        else:
            tags_str = " ".join(self.hashtags) if self.hashtags else ""

        parts = [header, "", body_text]
        if source_part:
            parts.extend(["", source_part])
        if tags_str:
            parts.extend(["", tags_str])
        return "\n".join(parts)


class ImageAsset(BaseModel):
    image_url: Optional[str] = None
    prompt_used: Optional[str] = None
    is_placeholder: bool = False


class PublishingJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: int
    source_input: str
    is_url: bool
    content_hash: str
    tone: Tone = Tone.DYNAMIC
    extracted_title: Optional[str] = None
    extracted_body: Optional[str] = None
    draft: Optional[PostContent] = None
    image: Optional[ImageAsset] = None
    status: JobStatus = JobStatus.PENDING
    channel_message_id: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(cls, user_id: int, source_input: str, tone: Tone = Tone.DYNAMIC) -> PublishingJob:
        stripped = source_input.strip()
        is_url = (stripped.startswith("http://") or stripped.startswith("https://")) and not any(c in stripped for c in " \t\r\n")
        c_hash = compute_content_hash(stripped)
        return cls(
            user_id=user_id,
            source_input=stripped,
            is_url=is_url,
            content_hash=c_hash,
            tone=tone,
            status=JobStatus.PENDING,
        )

    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def start_extracting(self) -> None:
        self.status = JobStatus.EXTRACTING
        self._touch()

    def set_extracted_content(self, title: str, body: str) -> None:
        self.extracted_title = title.strip()
        self.extracted_body = body.strip()
        self._touch()

    def set_draft(self, draft: PostContent) -> None:
        self.draft = draft
        self._touch()

    def set_image(self, image: ImageAsset) -> None:
        self.image = image
        self._touch()

    def mark_awaiting_approval(self) -> None:
        if not self.draft:
            raise ValueError("Draft is required before requesting approval")
        self.status = JobStatus.AWAITING_APPROVAL
        self._touch()

    def approve(self) -> None:
        if not self.draft:
            raise ValueError("Cannot approve job without draft")
        self.status = JobStatus.PUBLISHING
        self._touch()

    def mark_published(self, channel_message_id: int) -> None:
        self.channel_message_id = channel_message_id
        self.status = JobStatus.PUBLISHED
        self._touch()

    def reject(self) -> None:
        self.status = JobStatus.REJECTED
        self._touch()

    def fail(self, reason: str) -> None:
        self.error_message = reason
        self.status = JobStatus.FAILED
        self._touch()


class UserSettings(BaseModel):
    user_id: int
    preferred_tone: Tone = Tone.DYNAMIC
    preferred_image_model: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def update_tone(self, tone: Tone) -> None:
        self.preferred_tone = tone
        self.updated_at = datetime.now(timezone.utc)

    def update_image_model(self, model_name: Optional[str]) -> None:
        self.preferred_image_model = model_name
        self.updated_at = datetime.now(timezone.utc)

