from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class YouTubeConfig:
    enabled: bool
    client_id: str
    client_secret: str
    refresh_token: str
    privacy_status: str
    category_id: str
    max_attempts: int
    retry_seconds: int

    @classmethod
    def from_env(cls) -> "YouTubeConfig":
        privacy = os.getenv("YOUTUBE_PRIVACY_STATUS", "private").casefold()
        if privacy not in {"private", "unlisted", "public"}:
            privacy = "private"
        return cls(
            enabled=os.getenv("YOUTUBE_ENABLED", "false").casefold() in {"1", "true", "yes", "on"},
            client_id=os.getenv("YOUTUBE_CLIENT_ID", "").strip(),
            client_secret=os.getenv("YOUTUBE_CLIENT_SECRET", "").strip(),
            refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN", "").strip(),
            privacy_status=privacy,
            category_id=os.getenv("YOUTUBE_CATEGORY_ID", "17").strip() or "17",
            max_attempts=max(1, int(os.getenv("YOUTUBE_MAX_ATTEMPTS", "4"))),
            retry_seconds=max(30, int(os.getenv("YOUTUBE_RETRY_SECONDS", "900"))),
        )

    @property
    def ready(self) -> bool:
        return self.enabled and all((self.client_id, self.client_secret, self.refresh_token))


class PublicationStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout = 30000")
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS youtube_manifests (
                story_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                language TEXT NOT NULL,
                sources_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS youtube_publications (
                story_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                video_id TEXT,
                last_error TEXT,
                updated_at REAL NOT NULL,
                next_retry_at REAL NOT NULL DEFAULT 0
            )
            """
        )
        self.db.commit()

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        self.db.close()

    def remember(self, story_id: str, title: str, language: str, sources: list[str]) -> None:
        with self.db:
            self.db.execute(
                """
                INSERT OR IGNORE INTO youtube_manifests
                    (story_id, title, language, sources_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (story_id, title[:180], language, json.dumps(sources, ensure_ascii=False), time.time()),
            )

    def ready_jobs(self, limit: int = 2) -> list[dict]:
        rows = self.db.execute(
            """
            SELECT j.story_id, j.output_url, j.language,
                   COALESCE(m.title, 'Futbol gündeminde son dakika') AS title,
                   COALESCE(m.sources_json, '[]') AS sources_json
            FROM jobs j
            LEFT JOIN youtube_manifests m ON m.story_id = j.story_id
            LEFT JOIN youtube_publications p ON p.story_id = j.story_id
            WHERE j.status = 'complete' AND j.output_url IS NOT NULL
              AND (
                p.story_id IS NULL OR
                (p.status = 'failed' AND p.attempts < ? AND p.next_retry_at <= ?)
              )
            ORDER BY j.updated_at ASC
            LIMIT ?
            """,
            (YouTubeConfig.from_env().max_attempts, time.time(), max(1, limit)),
        ).fetchall()
        return [dict(row) for row in rows]

    def claim(self, story_id: str) -> bool:
        now = time.time()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT status, next_retry_at FROM youtube_publications WHERE story_id=?",
                (story_id,),
            ).fetchone()
            if row and (row["status"] in {"uploading", "published"} or float(row["next_retry_at"]) > now):
                return False
            self.db.execute(
                """
                INSERT INTO youtube_publications(story_id, status, attempts, updated_at)
                VALUES (?, 'uploading', 1, ?)
                ON CONFLICT(story_id) DO UPDATE SET
                    status='uploading', attempts=attempts+1,
                    last_error=NULL, updated_at=?, next_retry_at=0
                """,
                (story_id, now, now),
            )
            return True

    def published(self, story_id: str, video_id: str) -> None:
        with self.db:
            self.db.execute(
                """
                UPDATE youtube_publications
                SET status='published', video_id=?, last_error=NULL, updated_at=?, next_retry_at=0
                WHERE story_id=?
                """,
                (video_id, time.time(), story_id),
            )

    def failed(self, story_id: str, error: str, retry_seconds: int) -> None:
        now = time.time()
        with self.db:
            self.db.execute(
                """
                UPDATE youtube_publications
                SET status='failed', last_error=?, updated_at=?, next_retry_at=?
                WHERE story_id=?
                """,
                (error[:2000], now, now + retry_seconds, story_id),
            )

    def counts(self) -> dict[str, int]:
        rows = self.db.execute(
            "SELECT status, COUNT(*) AS count FROM youtube_publications GROUP BY status"
        ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}


def remember_manifest(db_path: str, story_id: str, title: str, language: str, sources: list[str]) -> None:
    with PublicationStore(db_path) as store:
        store.remember(story_id, title, language, sources)


def _download(url: str, destination: Path, api_key: str, timeout: int) -> None:
    if url.startswith("file://"):
        source = Path(urllib.request.url2pathname(urllib.parse.urlsplit(url).path))
        shutil.copyfile(source, destination)
    else:
        headers = {"User-Agent": "ViralFutbol/1.0"}
        if api_key:
            headers["x-api-key"] = api_key
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=max(30, timeout)) as response, destination.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    if destination.stat().st_size < 1024 or b"ftyp" not in destination.read_bytes()[:64]:
        raise ValueError("Video output is not a valid MP4")


def _metadata(job: dict) -> tuple[str, str, list[str]]:
    language = str(job.get("language") or "tr")
    raw_title = str(job.get("title") or "Futbol gündeminde son dakika").strip()
    title = raw_title[:92].rstrip(" #") + " #Shorts"
    sources = json.loads(job.get("sources_json") or "[]")
    if language == "en":
        description = "Verified football update with original narration and editing.\n\n#Football #Shorts"
        tags = ["football", "football news", "shorts"]
    else:
        description = "Doğrulanmış futbol gündemi; özgün anlatım ve kurgu.\n\n#Futbol #SonDakika #Shorts"
        tags = ["futbol", "son dakika", "futbol haberleri", "shorts"]
    if sources:
        description += "\n\nKaynak yayıncılar: " + ", ".join(str(x) for x in sources[:5])
    return title[:100], description[:5000], tags


def _upload(path: Path, job: dict, config: YouTubeConfig) -> str:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    credentials = Credentials(
        token=None,
        refresh_token=config.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.client_id,
        client_secret=config.client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    title, description, tags = _metadata(job)
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": config.category_id,
                "defaultLanguage": str(job.get("language") or "tr"),
            },
            "status": {
                "privacyStatus": config.privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        },
        media_body=MediaFileUpload(str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True),
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    video_id = str((response or {}).get("id") or "")
    if not video_id:
        raise RuntimeError("YouTube accepted upload without a video id")
    return video_id


def publish_ready(settings, limit: int = 2) -> dict:
    config = YouTubeConfig.from_env()
    result = {"enabled": config.enabled, "ready": config.ready, "published": 0, "failed": 0, "skipped": 0}
    if not config.ready:
        return result

    with PublicationStore(settings.db_path) as store:
        for job in store.ready_jobs(limit):
            story_id = str(job["story_id"])
            if not store.claim(story_id):
                result["skipped"] += 1
                continue
            try:
                with tempfile.TemporaryDirectory(prefix="viral-futbol-") as directory:
                    video_path = Path(directory) / f"{story_id}.mp4"
                    _download(str(job["output_url"]), video_path, settings.mpt_api_key, settings.mpt_request_timeout)
                    video_id = _upload(video_path, job, config)
                store.published(story_id, video_id)
                result["published"] += 1
            except Exception as exc:
                store.failed(story_id, f"{type(exc).__name__}: {exc}", config.retry_seconds)
                result["failed"] += 1
                print(f"ViralFutbol YouTube upload failed ({story_id}): {exc}", flush=True)
        result["status_counts"] = store.counts()
    return result
