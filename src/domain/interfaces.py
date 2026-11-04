from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from src.domain.models import PublishingJob, Tone, PostContent, ImageAsset, JobStatus, UserSettings


class ISettingsRepository(ABC):
    @abstractmethod
    async def get_user_settings(self, user_id: int, default_tone: Tone = Tone.DYNAMIC) -> UserSettings:
        """Retrieve settings for a user, or return defaults."""
        pass

    @abstractmethod
    async def save_user_settings(self, settings: UserSettings) -> None:
        """Persist user settings."""
        pass


class IJobRepository(ABC):
    @abstractmethod
    async def save(self, job: PublishingJob) -> None:
        """Save or update a publishing job."""
        pass

    @abstractmethod
    async def get_by_id(self, job_id: str) -> Optional[PublishingJob]:
        """Retrieve a job by its unique ID."""
        pass

    @abstractmethod
    async def get_by_hash(self, content_hash: str) -> Optional[PublishingJob]:
        """Retrieve a job by content hash for deduplication."""
        pass

    @abstractmethod
    async def get_by_status(self, status: JobStatus) -> List[PublishingJob]:
        """Retrieve all jobs currently in a given status."""
        pass


class IArticleExtractor(ABC):
    @abstractmethod
    async def extract(self, url: str) -> Tuple[str, str]:
        """
        Extracts clean title and body text from a webpage URL.
        Returns: (title, body)
        Raises: ValueError or ExtractionError on unrecoverable failure.
        """
        pass


class ILLMRewriter(ABC):
    @abstractmethod
    async def rewrite(self, raw_text: str, tone: Tone, title_hint: Optional[str] = None) -> PostContent:
        """
        Rewrites source text into a structured Telegram post draft.
        Returns: PostContent(title, body, hashtags)
        """
        pass


class IImageGenerator(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> ImageAsset:
        """
        Generates an image asset for the post.
        Returns: ImageAsset with image_url (or local file path) or placeholder.
        """
        pass


class IPublisher(ABC):
    @abstractmethod
    async def publish_to_channel(self, channel_id: str, draft: PostContent, image: Optional[ImageAsset] = None) -> int:
        """
        Publishes the finalized post to the target Telegram channel.
        Returns: Telegram message ID of the published post.
        """
        pass
