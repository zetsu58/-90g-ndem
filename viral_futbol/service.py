from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

from .config import Settings


@dataclass(frozen=True)
class Story:
    title: str
    url: str
    publisher: str
    published: datetime


def _clean_title(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+-\s+[^-]{2,50}$", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _tokens(value: str) -> set[str]:
    normalized = value.casefold().replace("ı", "i")
    return set(re.findall(r"[a-zçğıöşü0-9]{3,}", normalized))


def title_similarity(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    jaccard = len(a & b) / max(1, len(a | b))
    sequence = SequenceMatcher(None, left.casefold(), right.casefold()).ratio()
    return max(jaccard, sequence)


def publisher_family(value: str) -> str:
    """Collapse sibling labels such as 'NTV Haber' and 'NTVSpor'."""
    normalized = re.sub(r"[^a-zçğıöşü0-9]", "", value.casefold().replace("ı", "i"))
    noise = ("haberleri", "gazetesi", "haber", "spor", "tv", "comtr", "com")
    for suffix in noise:
        if normalized.endswith(suffix) and len(normalized) > len(suffix) + 2:
            normalized = normalized[: -len(suffix)]
            break
    return normalized


def fetch_google_news(
    query: str,
    timeout: int = 20,
    *,
    language: str = "tr",
    country: str = "TR",
) -> list[Story]:
    encoded = urllib.parse.quote_plus(query)
    url = (
        f"https://news.google.com/rss/search?q={encoded}"
        f"&hl={language}&gl={country}&ceid={country}:{language}"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "ViralFutbol/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        root = ET.fromstring(response.read())
    stories: list[Story] = []
    for item in root.findall("./channel/item"):
        title = _clean_title(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        source = item.find("source")
        publisher = (source.text or "").strip() if source is not None else urlparse(link).netloc
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "").astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue
        if title and link and publisher:
            stories.append(Story(title, link, publisher, published))
    return stories


def _fetch_queries(
    queries: tuple[str, ...],
    *,
    language: str,
    country: str,
    workers: int,
) -> list[Story]:
    """Fetch independent RSS searches concurrently so adding English stays fast."""
    stories: list[Story] = []
    max_workers = max(1, min(workers, len(queries)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                fetch_google_news,
                query,
                language=language,
                country=country,
            ): query
            for query in queries
        }
        for future in as_completed(futures):
            try:
                stories.extend(future.result())
            except Exception as exc:
                print(f"ViralFutbol feed error ({language}, {futures[future]}): {exc}")
    return stories


def news_editions(settings: Settings) -> list[tuple[str, str, tuple[str, ...]]]:
    editions: list[tuple[str, str, tuple[str, ...]]] = []
    if "tr" in settings.languages:
        editions.append(("tr", "TR", settings.queries))
    if "en" in settings.languages:
        editions.append(("en", "US", settings.global_queries))
    return editions


def verified_clusters(stories: list[Story], settings: Settings) -> list[list[Story]]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.max_age_minutes)
    recent = [s for s in stories if s.published >= cutoff]
    clusters: list[list[Story]] = []
    for story in sorted(recent, key=lambda x: x.published, reverse=True):
        for cluster in clusters:
            if title_similarity(story.title, cluster[0].title) >= settings.similarity:
                cluster.append(story)
                break
        else:
            clusters.append([story])
    return [
        c for c in clusters
        if len({publisher_family(s.publisher) for s in c}) >= settings.min_sources
    ]


class Store:
    def __init__(self, filename: str):
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(filename, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout = 30000")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA synchronous = FULL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS published "
            "(story_id TEXT PRIMARY KEY, task_id TEXT, created_at TEXT)"
        )
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                story_id TEXT PRIMARY KEY,
                language TEXT NOT NULL,
                task_id TEXT,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                output_url TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                next_retry_at REAL NOT NULL DEFAULT 0
            )
            """
        )
        # Preserve deduplication records created by version 0.1. Legacy rows do
        # not contain enough information to re-query MPT, so treat them as
        # complete rather than silently generating duplicate Shorts.
        now = time.time()
        self.db.execute(
            """
            INSERT OR IGNORE INTO jobs(
                story_id, language, task_id, status, attempts,
                created_at, updated_at, next_retry_at
            )
            SELECT story_id, 'tr', task_id, 'complete', 1, ?, ?, 0
            FROM published
            """,
            (now, now),
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    @staticmethod
    def story_id(cluster: list[Story], language: str = "tr") -> str:
        canonical = " ".join(sorted(_tokens(cluster[0].title)))
        return hashlib.sha256(f"{language}:{canonical}".encode()).hexdigest()[:24]

    def contains(self, story_id: str) -> bool:
        row = self.db.execute(
            "SELECT status FROM jobs WHERE story_id=?", (story_id,)
        ).fetchone()
        return row is not None and row["status"] in {
            "submitting",
            "submitted",
            "processing",
            "complete",
        }

    def save(self, story_id: str, task_id: str) -> None:
        now = time.time()
        self.db.execute(
            "INSERT OR IGNORE INTO published VALUES (?, ?, ?)",
            (story_id, task_id, datetime.now(timezone.utc).isoformat()),
        )
        self.db.execute(
            """
            INSERT INTO jobs(
                story_id, language, task_id, status, attempts,
                created_at, updated_at, next_retry_at
            ) VALUES (?, 'tr', ?, 'complete', 1, ?, ?, 0)
            ON CONFLICT(story_id) DO UPDATE SET
                task_id=excluded.task_id,
                status='complete',
                updated_at=excluded.updated_at,
                next_retry_at=0
            """,
            (story_id, task_id, now, now),
        )
        self.db.commit()

    def reserve(
        self,
        story_id: str,
        language: str,
        *,
        max_attempts: int,
        stale_seconds: int,
    ) -> bool:
        """Atomically reserve a story for one submission attempt."""
        now = time.time()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT * FROM jobs WHERE story_id=?", (story_id,)
            ).fetchone()
            if row:
                if row["status"] == "complete":
                    return False
                if row["status"] in {"submitted", "processing"}:
                    return False
                if (
                    row["status"] == "submitting"
                    and now - float(row["updated_at"]) < stale_seconds
                ):
                    return False
                if int(row["attempts"]) >= max_attempts:
                    return False
                if float(row["next_retry_at"] or 0) > now:
                    return False
                self.db.execute(
                    """
                    UPDATE jobs SET language=?, status='submitting',
                        attempts=attempts+1, last_error=NULL,
                        updated_at=?, next_retry_at=0
                    WHERE story_id=?
                    """,
                    (language, now, story_id),
                )
                return True

            self.db.execute(
                """
                INSERT INTO jobs(
                    story_id, language, status, attempts,
                    created_at, updated_at, next_retry_at
                ) VALUES (?, ?, 'submitting', 1, ?, ?, 0)
                """,
                (story_id, language, now, now),
            )
            return True

    def mark_submitted(self, story_id: str, task_id: str) -> None:
        with self.db:
            self.db.execute(
                """
                UPDATE jobs SET task_id=?, status='submitted',
                    last_error=NULL, updated_at=?
                WHERE story_id=?
                """,
                (task_id, time.time(), story_id),
            )

    def mark_processing(self, story_id: str) -> None:
        with self.db:
            self.db.execute(
                "UPDATE jobs SET status='processing', updated_at=? WHERE story_id=?",
                (time.time(), story_id),
            )

    def mark_complete(self, story_id: str, output_url: str) -> None:
        with self.db:
            self.db.execute(
                """
                UPDATE jobs SET status='complete', output_url=?,
                    last_error=NULL, updated_at=?, next_retry_at=0
                WHERE story_id=?
                """,
                (output_url, time.time(), story_id),
            )

    def mark_failed(self, story_id: str, error: str, retry_delay: int) -> None:
        now = time.time()
        with self.db:
            self.db.execute(
                """
                UPDATE jobs SET status='failed', last_error=?,
                    updated_at=?, next_retry_at=? WHERE story_id=?
                """,
                (error[:2000], now, now + max(0, retry_delay), story_id),
            )

    def active_jobs(self) -> list[dict]:
        rows = self.db.execute(
            """
            SELECT * FROM jobs
            WHERE status IN ('submitted', 'processing')
            ORDER BY updated_at ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def active_count(self) -> int:
        return int(
            self.db.execute(
                "SELECT COUNT(*) FROM jobs "
                "WHERE status IN ('submitting', 'submitted', 'processing')"
            ).fetchone()[0]
        )

    def status_counts(self) -> dict[str, int]:
        rows = self.db.execute(
            "SELECT status, COUNT(*) AS count FROM jobs GROUP BY status"
        ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}


def build_payload(cluster: list[Story], settings: Settings, language: str = "tr") -> dict:
    facts = "\n".join(f"- {s.publisher}: {s.title}" for s in cluster[:5])
    sources = "\n".join(f"- {s.publisher}: {s.url}" for s in cluster[:5])

    if language == "en":
        prompt = f"""Write a distinct 30-40 second English YouTube Shorts script from the verified football update below.
Use only facts shared by the supplied headlines. Do not invent quotes, fees, medical results, completion status, or motives.
Do not simply read or translate a headline. Open with an accurate hook, explain briefly why the confirmed update matters, and end with one natural question.
Use neutral, conversational global English. Do not read source URLs aloud. Keep it between 75 and 100 words.

Verified records:
{facts}

Sources (metadata only):
{sources}"""
        system_prompt = (
            "You are a careful global football news editor. Accuracy and original "
            "editorial value matter more than speed or hype."
        )
        voice_name = settings.english_voice_name
        font_size = 64
    else:
        prompt = f"""Aşağıdaki doğrulanmış futbol haberinden özgün, 30-40 saniyelik Türkçe YouTube Shorts metni yaz.
Yalnızca verilen başlıklardaki ortak gerçekleri kullan; tahmin, uydurma alıntı, ücret, sağlık sonucu veya kesinleşmemiş transfer durumu ekleme.
Haberi yalnızca okumakla yetinme: doğru bir kancayla başla, doğrulanmış gelişmenin neden önemli olduğunu kısaca açıkla ve doğal bir soruyla bitir.
Kaynak URL'lerini seslendirme. 75-100 kelimeyi aşma.

Doğrulanmış kayıtlar:
{facts}

Kaynaklar (yalnızca metadata):
{sources}"""
        system_prompt = (
            "Sen doğruluğu, özgün editoryal değeri ve izleyici güvenini hızdan ve "
            "sansasyondan önemli gören deneyimli bir Türk futbol haber editörüsün."
        )
        voice_name = settings.voice_name
        font_size = 70

    return {
        "video_subject": cluster[0].title,
        "video_script_prompt": prompt,
        "custom_system_prompt": system_prompt,
        "video_aspect": "9:16",
        "video_language": language,
        "voice_name": voice_name,
        "voice_rate": settings.voice_rate,
        "video_source": settings.video_source,
        "video_concat_mode": "sequential",
        "video_transition_mode": "Shuffle",
        "video_clip_duration": max(3, settings.video_clip_duration),
        "match_materials_to_script": True,
        "bgm_type": settings.bgm_type,
        "bgm_volume": settings.bgm_volume,
        "subtitle_enabled": True,
        "subtitle_position": "center",
        "font_size": font_size,
        "stroke_width": 2.5,
        "video_count": 1,
    }


def submit(
    payload: dict,
    settings: Settings,
    *,
    idempotency_key: str = "",
) -> str:
    if settings.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return "dry-run"
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if settings.mpt_api_key:
        headers["x-api-key"] = settings.mpt_api_key
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    request = urllib.request.Request(
        f"{settings.mpt_url.rstrip('/')}/videos",
        data=body,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(
        request, timeout=max(5, settings.mpt_request_timeout)
    ) as response:
        result = json.loads(response.read())
    data = result.get("data") or result
    task_id = data.get("task_id") or data.get("id")
    if not task_id:
        raise ValueError("MoneyPrinterTurbo accepted the request without a task id")
    return str(task_id)


def query_task(task_id: str, settings: Settings) -> dict:
    headers = {}
    if settings.mpt_api_key:
        headers["x-api-key"] = settings.mpt_api_key
    request = urllib.request.Request(
        f"{settings.mpt_url.rstrip('/')}/tasks/{urllib.parse.quote(task_id)}",
        headers=headers,
    )
    with urllib.request.urlopen(
        request, timeout=max(5, settings.mpt_request_timeout)
    ) as response:
        result = json.loads(response.read())
    data = result.get("data") or result
    if not isinstance(data, dict):
        raise ValueError("MoneyPrinterTurbo returned an invalid task response")
    return data


def _absolute_output_url(value: str, settings: Settings) -> str:
    if value.startswith(("http://", "https://")):
        return value
    parsed = urllib.parse.urlsplit(settings.mpt_url)
    origin = f"{parsed.scheme}://{parsed.netloc}/"
    return urllib.parse.urljoin(origin, value.lstrip("/"))


def reconcile_jobs(store: Store, settings: Settings) -> dict[str, int]:
    result = {"completed": 0, "failed": 0, "processing": 0, "unreachable": 0}
    for job in store.active_jobs():
        story_id = job["story_id"]
        task_id = job.get("task_id")
        if not task_id:
            store.mark_failed(
                story_id,
                "submitted job has no MoneyPrinterTurbo task id",
                settings.retry_delay_seconds,
            )
            result["failed"] += 1
            continue
        try:
            task = query_task(task_id, settings)
        except Exception as exc:
            # A temporary tunnel/Colab outage must not consume another attempt.
            # The job stays active and will be reconciled on the next /run.
            result["unreachable"] += 1
            print(f"ViralFutbol task query deferred ({task_id}): {exc}")
            continue

        try:
            state = int(task.get("state", 0))
        except (TypeError, ValueError):
            state = 0
        if state == 1:
            videos = task.get("videos") or []
            if not videos:
                store.mark_failed(
                    story_id,
                    "MoneyPrinterTurbo completed without a video output",
                    settings.retry_delay_seconds,
                )
                result["failed"] += 1
                continue
            store.mark_complete(
                story_id,
                _absolute_output_url(str(videos[0]), settings),
            )
            result["completed"] += 1
        elif state == -1:
            error = str(task.get("error") or "MoneyPrinterTurbo task failed")
            store.mark_failed(story_id, error, settings.retry_delay_seconds)
            result["failed"] += 1
        else:
            store.mark_processing(story_id)
            result["processing"] += 1
    return result


def run_once(settings: Settings) -> dict:
    with Store(settings.db_path) as store:
        reconciliation = (
            {"completed": 0, "failed": 0, "processing": 0, "unreachable": 0}
            if settings.dry_run
            else reconcile_jobs(store, settings)
        )
        diagnostics = {
            "fetched": 0,
            "recent": 0,
            "verified": 0,
            "duplicates": 0,
            "submitted": 0,
            "submission_failed": 0,
            "deferred_capacity": 0,
            "deferred_retry": 0,
            "dry_run": settings.dry_run,
            "languages": {},
            "selected": [],
        }
        cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=settings.max_age_minutes
        )
        available_slots = max(
            0, max(1, settings.max_inflight_tasks) - store.active_count()
        )
        for language, country, queries in news_editions(settings):
            stories = _fetch_queries(
                queries,
                language=language,
                country=country,
                workers=settings.fetch_workers,
            )
            recent = [story for story in stories if story.published >= cutoff]
            clusters = verified_clusters(stories, settings)
            language_diagnostics = {
                "fetched": len(stories),
                "recent": len(recent),
                "verified": len(clusters),
                "duplicates": 0,
                "submitted": 0,
                "submission_failed": 0,
                "deferred_capacity": 0,
                "deferred_retry": 0,
            }
            diagnostics["fetched"] += len(stories)
            diagnostics["recent"] += len(recent)
            diagnostics["verified"] += len(clusters)

            for cluster in clusters:
                story_id = store.story_id(cluster, language)
                if settings.dry_run:
                    submit(
                        build_payload(cluster, settings, language),
                        settings,
                        idempotency_key=f"viral-futbol:{story_id}",
                    )
                    diagnostics["submitted"] += 1
                    language_diagnostics["submitted"] += 1
                    diagnostics["selected"].append(
                        {
                            "language": language,
                            "title": cluster[0].title,
                            "sources": sorted({story.publisher for story in cluster}),
                            "task_id": "dry-run",
                        }
                    )
                    continue
                if store.contains(story_id):
                    diagnostics["duplicates"] += 1
                    language_diagnostics["duplicates"] += 1
                    continue
                if available_slots <= 0:
                    diagnostics["deferred_capacity"] += 1
                    language_diagnostics["deferred_capacity"] += 1
                    continue
                if not store.reserve(
                    story_id,
                    language,
                    max_attempts=max(1, settings.max_task_attempts),
                    stale_seconds=max(60, settings.submission_stale_seconds),
                ):
                    diagnostics["deferred_retry"] += 1
                    language_diagnostics["deferred_retry"] += 1
                    continue
                try:
                    task_id = submit(
                        build_payload(cluster, settings, language),
                        settings,
                        idempotency_key=f"viral-futbol:{story_id}",
                    )
                    store.mark_submitted(story_id, task_id)
                    diagnostics["submitted"] += 1
                    language_diagnostics["submitted"] += 1
                    available_slots -= 1
                    diagnostics["selected"].append(
                        {
                            "language": language,
                            "title": cluster[0].title,
                            "sources": sorted({story.publisher for story in cluster}),
                            "task_id": task_id,
                        }
                    )
                except Exception as exc:
                    store.mark_failed(
                        story_id,
                        f"submission failed: {exc}",
                        settings.retry_delay_seconds,
                    )
                    diagnostics["submission_failed"] += 1
                    language_diagnostics["submission_failed"] += 1
            diagnostics["languages"][language] = language_diagnostics

        diagnostics.update(reconciliation)
        diagnostics["active"] = store.active_count()
        diagnostics["status_counts"] = store.status_counts()
        print(
            "ViralFutbol diagnostics: "
            + json.dumps(diagnostics, ensure_ascii=False),
            flush=True,
        )
        return diagnostics


def main() -> None:
    settings = Settings()
    while True:
        try:
            summary = run_once(settings)
            print(f"ViralFutbol: {json.dumps(summary, ensure_ascii=False)}")
        except Exception as exc:
            print(f"ViralFutbol error: {exc}")
        time.sleep(max(60, settings.poll_seconds))


if __name__ == "__main__":
    main()

