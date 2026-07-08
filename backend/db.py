"""Minimal sqlite3-based metadata store for generated images."""
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

_lock = threading.Lock()
_db_path: Optional[str] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS images (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    prompt TEXT,
    negative_prompt TEXT,
    width INTEGER,
    height INTEGER,
    steps INTEGER,
    guidance_scale REAL,
    seed INTEGER,
    source_image_id TEXT,
    filename TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def init_db(outputs_dir: str) -> None:
    global _db_path
    os.makedirs(outputs_dir, exist_ok=True)
    _db_path = os.path.join(outputs_dir, "metadata.db")
    with _connect() as conn:
        conn.execute(SCHEMA)
        conn.commit()


@contextmanager
def _connect():
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def insert_image(record: dict[str, Any]) -> None:
    with _lock, _connect() as conn:
        conn.execute(
            """
            INSERT INTO images
                (id, type, prompt, negative_prompt, width, height, steps,
                 guidance_scale, seed, source_image_id, filename, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["type"],
                record.get("prompt"),
                record.get("negative_prompt"),
                record.get("width"),
                record.get("height"),
                record.get("steps"),
                record.get("guidance_scale"),
                record.get("seed"),
                record.get("source_image_id"),
                record["filename"],
                record["created_at"],
            ),
        )
        conn.commit()


def list_images() -> list[dict[str, Any]]:
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT * FROM images ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


def get_image(image_id: str) -> Optional[dict[str, Any]]:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
        return dict(row) if row else None


def delete_image(image_id: str) -> bool:
    with _lock, _connect() as conn:
        cur = conn.execute("DELETE FROM images WHERE id = ?", (image_id,))
        conn.commit()
        return cur.rowcount > 0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
