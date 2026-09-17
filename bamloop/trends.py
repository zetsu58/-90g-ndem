from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from difflib import SequenceMatcher


@dataclass
class TrendCandidate:
    title: str
    url: str = ""
    source: str = ""
    published_at: str = ""
    engagement: int = 0
    score: int = 0
    fingerprint: str = ""


BIG_TOPICS = (
    "galatasaray", "fenerbahçe", "fenerbahce", "beşiktaş", "besiktas",
    "trabzonspor", "şampiyonlar ligi", "champions league", "transfer",
    "derbi", "messi", "ronaldo", "mbappe", "yamal", "osimhen",
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\wçğıöşüÇĞİÖŞÜ ]+", " ", text.lower())).strip()


def fingerprint(text: str) -> str:
    return hashlib.sha256(_clean(text).encode("utf-8")).hexdigest()[:16]


def viral_score(candidate: TrendCandidate, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    text = _clean(candidate.title)
    score = 25

    if any(topic in text for topic in BIG_TOPICS):
        score += 25
    if any(word in text for word in ("son dakika", "resmi", "açıkladı", "anlaşma", "gol", "kırmızı kart", "rekor")):
        score += 18
    score += min(20, max(0, candidate.engagement) // 250)

    if candidate.published_at:
        try:
            published = datetime.fromisoformat(candidate.published_at.replace("Z", "+00:00"))
            hours = max(0, (now - published).total_seconds() / 3600)
            score += 20 if hours <= 2 else 14 if hours <= 6 else 8 if hours <= 24 else 0
        except ValueError:
            pass

    return max(0, min(100, score))


def deduplicate(items: list[TrendCandidate], similarity: float = 0.78) -> list[TrendCandidate]:
    unique: list[TrendCandidate] = []
    for item in items:
        normalized = _clean(item.title)
        if not normalized:
            continue
        if any(SequenceMatcher(None, normalized, _clean(old.title)).ratio() >= similarity for old in unique):
            continue
        item.fingerprint = fingerprint(item.title)
        item.score = viral_score(item)
        unique.append(item)
    return sorted(unique, key=lambda x: x.score, reverse=True)


def content_brief(candidate: TrendCandidate) -> dict:
    return {
        "trend": asdict(candidate),
        "shorts": {
            "hook": f"Futbol gündeminde sıcak gelişme: {candidate.title}",
            "target_seconds": 25,
            "format": "9:16",
            "rules": [
                "İlk 2 saniyede merak uyandır",
                "Doğrulanmayan iddiayı kesin gerçek gibi sunma",
                "Kaynak metni kopyalama; özgün anlatım üret",
                "Kısa cümleler ve hızlı tempo kullan",
            ],
        },
        "social": {
            "x_style": "kısa, özgün, haber odaklı",
            "cta": "Sence bu gelişme takımı nasıl etkiler?",
        },
    }
