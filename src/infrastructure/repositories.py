import json
from datetime import datetime, timezone
from typing import List, Optional
import aiosqlite
from src.domain.interfaces import IJobRepository, ISettingsRepository
from src.domain.models import PublishingJob, JobStatus, Tone, PostContent, ImageAsset, UserSettings
from src.infrastructure.database import get_db_connection


class SqliteJobRepository(IJobRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _row_to_job(self, row: aiosqlite.Row) -> PublishingJob:
        # Retrieve source_url
        source_url = None
        if "source_url" in row.keys() and row["source_url"]:
            source_url = row["source_url"]
        elif row["is_url"]:
            source_url = row["source_input"]

        draft = None
        if row["rewritten_title"] and row["rewritten_body"]:
            hashtags = []
            if row["hashtags_json"]:
                try:
                    hashtags = json.loads(row["hashtags_json"])
                except Exception:
                    hashtags = []

            # Retrieve image_prompts
            image_prompts = []
            if "image_prompts_json" in row.keys() and row["image_prompts_json"]:
                try:
                    image_prompts = json.loads(row["image_prompts_json"])
                except Exception:
                    image_prompts = []

            # Retrieve keywords
            keywords = []
            if "keywords_json" in row.keys() and row["keywords_json"]:
                try:
                    keywords = json.loads(row["keywords_json"])
                except Exception:
                    keywords = []

            draft = PostContent(
                title=row["rewritten_title"],
                body=row["rewritten_body"],
                hashtags=hashtags,
                source_url=source_url,
                image_prompts=image_prompts,
                keywords=keywords,
            )

        image = None
        if row["image_url"] or row["image_prompt"] or row["is_image_placeholder"]:
            image = ImageAsset(
                image_url=row["image_url"],
                prompt_used=row["image_prompt"],
                is_placeholder=bool(row["is_image_placeholder"]),
            )

        created_at = datetime.fromisoformat(row["created_at"])
        updated_at = datetime.fromisoformat(row["updated_at"])

        return PublishingJob(
            id=row["id"],
            user_id=row["user_id"],
            source_input=row["source_input"],
            is_url=bool(row["is_url"]),
            content_hash=row["content_hash"],
            tone=Tone(row["tone"]),
            extracted_title=row["extracted_title"],
            extracted_body=row["extracted_body"],
            draft=draft,
            image=image,
            status=JobStatus(row["status"]),
            channel_message_id=row["channel_message_id"],
            source_url=source_url,
            error_message=row["error_message"],
            created_at=created_at,
            updated_at=updated_at,
        )

    async def save(self, job: PublishingJob) -> None:
        async with get_db_connection(self.db_path) as db:
            hashtags_json = json.dumps(job.draft.hashtags) if job.draft else None
            image_prompts_json = json.dumps(job.draft.image_prompts) if job.draft else None
            keywords_json = json.dumps(job.draft.keywords) if job.draft else None
            rewritten_title = job.draft.title if job.draft else None
            rewritten_body = job.draft.body if job.draft else None
            image_url = job.image.image_url if job.image else None
            image_prompt = job.image.prompt_used if job.image else None
            is_image_placeholder = 1 if (job.image and job.image.is_placeholder) else 0

            source_url = (job.draft.source_url if (job.draft and job.draft.source_url) else job.source_url) or (job.source_input if job.is_url else None)

            await db.execute(
                """
                INSERT INTO publishing_jobs (
                    id, user_id, source_input, is_url, content_hash, tone,
                    extracted_title, extracted_body, rewritten_title, rewritten_body,
                    hashtags_json, image_url, image_prompt, is_image_placeholder, source_url,
                    image_prompts_json, keywords_json,
                    status, channel_message_id, error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    user_id=excluded.user_id,
                    source_input=excluded.source_input,
                    is_url=excluded.is_url,
                    content_hash=excluded.content_hash,
                    tone=excluded.tone,
                    extracted_title=excluded.extracted_title,
                    extracted_body=excluded.extracted_body,
                    rewritten_title=excluded.rewritten_title,
                    rewritten_body=excluded.rewritten_body,
                    hashtags_json=excluded.hashtags_json,
                    image_url=excluded.image_url,
                    image_prompt=excluded.image_prompt,
                    is_image_placeholder=excluded.is_image_placeholder,
                    source_url=excluded.source_url,
                    image_prompts_json=excluded.image_prompts_json,
                    keywords_json=excluded.keywords_json,
                    status=excluded.status,
                    channel_message_id=excluded.channel_message_id,
                    error_message=excluded.error_message,
                    updated_at=excluded.updated_at;
                """,
                (
                    job.id,
                    job.user_id,
                    job.source_input,
                    1 if job.is_url else 0,
                    job.content_hash,
                    job.tone.value,
                    job.extracted_title,
                    job.extracted_body,
                    rewritten_title,
                    rewritten_body,
                    hashtags_json,
                    image_url,
                    image_prompt,
                    is_image_placeholder,
                    source_url,
                    image_prompts_json,
                    keywords_json,
                    job.status.value,
                    job.channel_message_id,
                    job.error_message,
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                ),
            )
            await db.commit()

    async def get_by_id(self, job_id: str) -> Optional[PublishingJob]:
        async with get_db_connection(self.db_path) as db:
            async with db.execute("SELECT * FROM publishing_jobs WHERE id = ?", (job_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return self._row_to_job(row)

    async def get_by_hash(self, content_hash: str) -> Optional[PublishingJob]:
        async with get_db_connection(self.db_path) as db:
            async with db.execute("SELECT * FROM publishing_jobs WHERE content_hash = ?", (content_hash,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return self._row_to_job(row)

    async def get_by_status(self, status: JobStatus) -> List[PublishingJob]:
        async with get_db_connection(self.db_path) as db:
            async with db.execute("SELECT * FROM publishing_jobs WHERE status = ? ORDER BY created_at ASC", (status.value,)) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_job(row) for row in rows]


class SqliteSettingsRepository(ISettingsRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def get_user_settings(self, user_id: int, default_tone: Tone = Tone.DYNAMIC) -> UserSettings:
        async with get_db_connection(self.db_path) as db:
            async with db.execute(
                "SELECT user_id, tone, image_model, updated_at FROM user_settings WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return UserSettings(
                        user_id=row["user_id"],
                        preferred_tone=Tone(row["tone"]),
                        preferred_image_model=row["image_model"],
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                    )
                return UserSettings(user_id=user_id, preferred_tone=default_tone)

    async def save_user_settings(self, settings: UserSettings) -> None:
        async with get_db_connection(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO user_settings (user_id, tone, image_model, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    tone=excluded.tone,
                    image_model=excluded.image_model,
                    updated_at=excluded.updated_at;
                """,
                (
                    settings.user_id,
                    settings.preferred_tone.value,
                    settings.preferred_image_model,
                    settings.updated_at.isoformat(),
                ),
            )
            await db.commit()

