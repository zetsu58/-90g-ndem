from __future__ import annotations

import re

from .topic_learning import topics_for


TEAM_HASHTAGS = {
    "galatasaray": "#Galatasaray",
    "fenerbahce": "#Fenerbahçe",
    "besiktas": "#Beşiktaş",
    "trabzonspor": "#Trabzonspor",
}
TOPIC_HASHTAGS = {
    "transfer": "#Transfer",
    "derbi": "#Derbi",
    "champions_league": "#ŞampiyonlarLigi",
    "injury": "#Sakatlık",
    "goal": "#Gol",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def discovery_metadata(title: str, language: str = "tr") -> dict:
    clean = _clean(title).rstrip(" .")
    topics = topics_for(clean)

    if language != "tr":
        short_title = clean[:88].rstrip(" -,:") + " #Shorts"
        return {
            "title": short_title[:100],
            "description": f"{clean}. Original football news summary and commentary.",
            "hashtags": ["#Football", "#Shorts"],
            "tags": ["football", "football news"],
        }

    # Accurate first; curiosity comes from compact packaging, never invented claims.
    prefix = "SON DAKİKA: " if any(x in clean.casefold() for x in ("resmi", "açıklandı", "son dakika")) else ""
    base = prefix + clean
    yt_title = base[:90].rstrip(" -,:") + " #Shorts"

    hashtags = []
    for topic in sorted(topics):
        if topic in TEAM_HASHTAGS:
            hashtags.append(TEAM_HASHTAGS[topic])
        elif topic in TOPIC_HASHTAGS:
            hashtags.append(TOPIC_HASHTAGS[topic])
    hashtags.extend(["#Futbol", "#Shorts"])
    hashtags = list(dict.fromkeys(hashtags))[:5]

    description = (
        f"{clean}. 90+ Gündem bu gelişmeyi kısa, özgün ve hızlı bir özetle aktarıyor. "
        f"Yeni doğrulanmış gelişmeler için kanalı takip et.\n\n{' '.join(hashtags)}"
    )

    tags = ["futbol", "futbol haberleri", "son dakika futbol"]
    for topic in sorted(topics):
        tags.append(topic.replace("_", " "))
    return {
        "title": yt_title[:100],
        "description": description,
        "hashtags": hashtags,
        "tags": list(dict.fromkeys(tags))[:10],
    }
