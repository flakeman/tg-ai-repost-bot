import os
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
    status TEXT NOT NULL,
    channel_message_id INTEGER,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_hash ON publishing_jobs(content_hash);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON publishing_jobs(status);
"""


async def init_db(db_path: str) -> None:
    dirname = os.path.dirname(db_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()
