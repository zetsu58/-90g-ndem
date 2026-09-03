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
    normalized = re.sub(r"[^a-zçğıöşü0-9]", "", value.casefold().replace("ı", "i"))
    noise = ("haberleri", "gazetesi", "haber", "spor", "tv", "comtr", "com")
    for suffix in noise:
        if normalized.endswith(suffix) and len(normalized) > len(suffix) + 2:
            normalized = normalized[: -len(suffix)]
            break
    return normalized


def fetch_google_news(query: str, timeout: int = 20, *, language: str = "tr", country: str = "TR") -> list[Story]:
    encoded = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl={language}&gl={country}&ceid={country}:{language}"
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


def _fetch_queries(queries: tuple[str, ...], *, language: str, country: str, workers: int) -> list[Story]:
    stories: list[Story] = []
    max_workers = max(1, min(workers, len(queries)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_google_news, query, language=language, country=country): query for query in queries}
        for future in as_completed(futures):
            try:
                stories.extend(future.result())
            except Exception as exc:
                print(f"ViralFutbol feed error ({language}, {futures[future]}): {exc}", flush=True)
    return stories


def news_editions(settings: Settings) -> list[tuple[str, str, tuple[str, ...]]]:
    editions = []
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
    return [c for c in clusters if len({publisher_family(s.publisher) for s in c}) >= settings.min_sources]


class Store:
    def __init__(self, filename: str):
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(filename)
        self.db.execute("CREATE TABLE IF NOT EXISTS published (story_id TEXT PRIMARY KEY, task_id TEXT, created_at TEXT)")
        self.db.commit()

    @staticmethod
    def story_id(cluster: list[Story], language: str = "tr") -> str:
        canonical = " ".join(sorted(_tokens(cluster[0].title)))
        return hashlib.sha256(f"{language}:{canonical}".encode()).hexdigest()[:24]

    def contains(self, story_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM published WHERE story_id=?", (story_id,)).fetchone() is not None

    def save(self, story_id: str, task_id: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO published VALUES (?, ?, ?)", (story_id, task_id, datetime.now(timezone.utc).isoformat()))
        self.db.commit()


def build_payload(cluster: list[Story], settings: Settings, language: str = "tr") -> dict:
    facts = "\n".join(f"- {s.publisher}: {s.title}" for s in cluster[:5])
    sources = "\n".join(f"- {s.publisher}: {s.url}" for s in cluster[:5])
    if language == "en":
        prompt = f"Write a distinct 30-40 second English YouTube Shorts script from the verified football update below.\nUse only facts shared by the supplied headlines. Do not invent quotes, fees, medical results, completion status, or motives.\nOpen with an accurate hook, explain briefly why it matters, and end with one natural question. Keep it between 75 and 100 words.\n\nVerified records:\n{facts}\n\nSources:\n{sources}"
        system_prompt = "You are a careful global football news editor. Accuracy and original editorial value matter more than speed or hype."
        voice_name, font_size = settings.english_voice_name, 64
    else:
        prompt = f"Aşağıdaki doğrulanmış futbol haberinden özgün, 30-40 saniyelik Türkçe YouTube Shorts metni yaz.\nYalnızca verilen başlıklardaki ortak gerçekleri kullan; tahmin veya kesinleşmemiş transfer durumu ekleme. Doğru bir kancayla başla, neden önemli olduğunu açıkla ve doğal bir soruyla bitir. 75-100 kelimeyi aşma.\n\nDoğrulanmış kayıtlar:\n{facts}\n\nKaynaklar:\n{sources}"
        system_prompt = "Sen doğruluğu ve izleyici güvenini sansasyondan önemli gören deneyimli bir Türk futbol haber editörüsün."
        voice_name, font_size = settings.voice_name, 70
    return {"video_subject": cluster[0].title, "video_script_prompt": prompt, "custom_system_prompt": system_prompt, "video_aspect": "9:16", "video_language": language, "voice_name": voice_name, "voice_rate": settings.voice_rate, "video_source": settings.video_source, "video_concat_mode": "sequential", "video_clip_duration": max(3, settings.video_clip_duration), "match_materials_to_script": True, "bgm_type": settings.bgm_type, "bgm_volume": settings.bgm_volume, "subtitle_enabled": True, "subtitle_position": "center", "font_size": font_size, "stroke_width": 2.5, "video_count": 1}


def submit(payload: dict, settings: Settings) -> str:
    if settings.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
        return "dry-run"
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if settings.mpt_api_key:
        headers["Authorization"] = f"Bearer {settings.mpt_api_key}"
    request = urllib.request.Request(f"{settings.mpt_url.rstrip('/')}/videos", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read())
    data = result.get("data") or result
    return str(data.get("task_id") or data.get("id") or "submitted")


def run_once(settings: Settings) -> dict:
    store = Store(settings.db_path)
    diag = {"fetched": 0, "recent": 0, "verified": 0, "duplicates": 0, "submitted": 0, "dry_run": settings.dry_run, "languages": {}, "selected": []}
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.max_age_minutes)
    for language, country, queries in news_editions(settings):
        stories = _fetch_queries(queries, language=language, country=country, workers=settings.fetch_workers)
        recent = [s for s in stories if s.published >= cutoff]
        clusters = verified_clusters(stories, settings)
        lang = {"fetched": len(stories), "recent": len(recent), "verified": len(clusters), "duplicates": 0, "submitted": 0}
        diag["fetched"] += len(stories)
        diag["recent"] += len(recent)
        diag["verified"] += len(clusters)
        for cluster in clusters:
            story_id = store.story_id(cluster, language)
            if store.contains(story_id):
                lang["duplicates"] += 1
                diag["duplicates"] += 1
                continue
            task_id = submit(build_payload(cluster, settings, language), settings)
            store.save(story_id, task_id)
            lang["submitted"] += 1
            diag["submitted"] += 1
            diag["selected"].append({"language": language, "title": cluster[0].title, "sources": sorted({s.publisher for s in cluster}), "task_id": task_id})
        diag["languages"][language] = lang
    print("ViralFutbol diagnostics: " + json.dumps(diag, ensure_ascii=False), flush=True)
    return diag


def main() -> None:
    settings = Settings()
    while True:
        try:
            result = run_once(settings)
            print(f"ViralFutbol: {result['submitted']} new verified task(s) submitted.", flush=True)
        except Exception as exc:
            print(f"ViralFutbol error: {exc}", flush=True)
        time.sleep(max(60, settings.poll_seconds))


if __name__ == "__main__":
    main()
