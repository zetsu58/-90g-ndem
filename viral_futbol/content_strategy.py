from __future__ import annotations

from dataclasses import asdict, dataclass

from .creative_learning import creative_report, recommended_hook, recommended_time_bucket
from .topic_learning import topic_boost, topics_for


@dataclass(frozen=True)
class ContentStrategy:
    title: str
    topics: tuple[str, ...]
    hook: str
    publish_window: str | None
    topic_boost: float
    confidence: str
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


def build_content_strategy(db_path: str, title: str) -> ContentStrategy:
    topics = tuple(sorted(topics_for(title)))
    boost, topic_evidence = topic_boost(db_path, title)
    report = creative_report(db_path)
    hook = recommended_hook(db_path) or "direct"
    window = recommended_time_bucket(db_path)

    hook_samples = int((report.get("hooks", {}).get(hook) or {}).get("samples", 0))
    window_samples = int((report.get("hours", {}).get(window) or {}).get("samples", 0)) if window else 0
    total_samples = int(report.get("samples", 0))

    if total_samples >= 30 and hook_samples >= 8 and (not window or window_samples >= 8):
        confidence = "high"
    elif total_samples >= 10 and hook_samples >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    reasons = []
    if topic_evidence:
        reasons.append("topic:" + ",".join(topic_evidence))
    reasons.append(f"hook:{hook}:{hook_samples}")
    if window:
        reasons.append(f"window:{window}:{window_samples}")
    reasons.append(f"samples:{total_samples}")

    return ContentStrategy(
        title=title,
        topics=topics,
        hook=hook,
        publish_window=window,
        topic_boost=boost,
        confidence=confidence,
        reasons=tuple(reasons),
    )
