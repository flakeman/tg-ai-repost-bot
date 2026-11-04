import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import aiosqlite

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS publishing_jobs (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    source_input TEXT NOT NULL,
    is_url BOOLEAN NOT NULL,
    content_hash TEXT UNIQUE NOT NULL,
    tone TEXT NOT NULL,
    extracted_title TEXT,
    extracted_body TEXT,
    rewritten_title TEXT,
    rewritten_body TEXT,
    hashtags_json TEXT,
    image_url TEXT,
    image_prompt TEXT,
    is_image_placeholder BOOLEAN DEFAULT 0,
    source_url TEXT,
    status TEXT NOT NULL,
    channel_message_id INTEGER,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_hash ON publishing_jobs(content_hash);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON publishing_jobs(status);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    tone TEXT NOT NULL DEFAULT 'dynamic',
    image_model TEXT,
    updated_at TEXT NOT NULL
);
"""


@asynccontextmanager
async def get_db_connection(db_path: str) -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Central connection factory ensuring WAL mode and busy_timeout
    are always configured on every connection.
    """
    dirname = os.path.dirname(db_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA busy_timeout = 5000;")
        db.row_factory = aiosqlite.Row
        yield db


async def init_db(db_path: str) -> None:
    async with get_db_connection(db_path) as db:
        await db.executescript(SCHEMA_SQL)
        cursor = await db.execute("PRAGMA table_info(publishing_jobs);")
        columns = [row[1] for row in await cursor.fetchall()]
        if "source_url" not in columns:
            await db.execute("ALTER TABLE publishing_jobs ADD COLUMN source_url TEXT;")
        await db.commit()
