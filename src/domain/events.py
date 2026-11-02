from dataclasses import dataclass
from typing import Optional
from src.domain.models import PostContent, ImageAsset


@dataclass(frozen=True)
class JobCreatedEvent:
    job_id: str
    user_id: int
    content_hash: str


@dataclass(frozen=True)
class ArticleExtractedEvent:
    job_id: str
    title: str
    body_length: int


@dataclass(frozen=True)
class ContentRewrittenEvent:
    job_id: str
    draft: PostContent


@dataclass(frozen=True)
class ImageGeneratedEvent:
    job_id: str
    image_url: Optional[str]


@dataclass(frozen=True)
class AwaitingApprovalEvent:
    job_id: str
    draft: PostContent
    image: Optional[ImageAsset]


@dataclass(frozen=True)
class JobApprovedEvent:
    job_id: str
    user_id: int


@dataclass(frozen=True)
class JobPublishedEvent:
    job_id: str
    channel_message_id: int


@dataclass(frozen=True)
class JobFailedEvent:
    job_id: str
    reason: str
