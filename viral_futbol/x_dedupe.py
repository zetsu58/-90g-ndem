from __future__ import annotations

import hashlib
import re
import sqlite3
import time
from datetime import datetime, timezone
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
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS x_reservations ("
            "news_key TEXT PRIMARY KEY, reserved_at REAL NOT NULL)"
        )
        self.db.commit()

    def contains(self, title: str) -> bool:
        key = news_key(title)
        row = self.db.execute(
            "SELECT 1 FROM x_published WHERE news_key=? UNION SELECT 1 FROM x_reservations WHERE news_key=?",
            (key, key),
        ).fetchone()
        return row is not None

    def published_today(self) -> int:
        now = datetime.now(timezone.utc)
        start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp()
        row = self.db.execute(
            "SELECT COUNT(*) FROM x_published WHERE created_at>=?", (start,)
        ).fetchone()
        return int(row[0]) if row else 0

    def reserve(self, title: str, daily_limit: int) -> bool:
        """Atomically reserve a story only while the daily budget has room."""
        key = news_key(title)
        now = time.time()
        today = datetime.now(timezone.utc)
        start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc).timestamp()
        with self.db:
            self.db.execute("DELETE FROM x_reservations WHERE reserved_at<?", (now - 900,))
            published = self.db.execute(
                "SELECT COUNT(*) FROM x_published WHERE created_at>=?", (start,)
            ).fetchone()[0]
            reserved = self.db.execute(
                "SELECT COUNT(*) FROM x_reservations WHERE reserved_at>=?", (start,)
            ).fetchone()[0]
            if published + reserved >= max(0, daily_limit):
                return False
            try:
                self.db.execute(
                    "INSERT INTO x_reservations(news_key, reserved_at) VALUES (?, ?)", (key, now)
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def mark(self, title: str, external_id: str) -> None:
        key = news_key(title)
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO x_published(news_key, external_id, created_at) VALUES (?, ?, ?)",
                (key, external_id, time.time()),
            )
            self.db.execute("DELETE FROM x_reservations WHERE news_key=?", (key,))

    def release(self, title: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM x_reservations WHERE news_key=?", (news_key(title),))

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
