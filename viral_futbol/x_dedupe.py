from __future__ import annotations

import hashlib
import re
import sqlite3
import time
from pathlib import Path


def news_key(title: str) -> str:
    normalized = re.sub(r"\W+", " ", title.casefold()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


class XPublishedStore:
    def __init__(self, filename: str) -> None:
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(filename, timeout=30)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS x_published ("
            "news_key TEXT PRIMARY KEY, external_id TEXT, created_at REAL NOT NULL)"
        )
        self.db.commit()

    def contains(self, title: str) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM x_published WHERE news_key=?", (news_key(title),)
        ).fetchone()
        return row is not None

    def mark(self, title: str, external_id: str) -> None:
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO x_published(news_key, external_id, created_at) VALUES (?, ?, ?)",
                (news_key(title), external_id, time.time()),
            )

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
