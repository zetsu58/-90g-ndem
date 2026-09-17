from __future__ import annotations

from dataclasses import asdict, dataclass

from .editorial_visuals import build_visual_beats


@dataclass(frozen=True)
class TimelineShot:
    start: float
    duration: float
    kind: str
    subject: str
    motion: str
    transition: str


def build_video_timeline(title: str, target_seconds: float = 24.0) -> list[TimelineShot]:
    beats = build_visual_beats(title)
    # Motion-first: no still is allowed to sit unchanged for the full beat.
    durations = [2.2, 2.8, 3.0, 2.6]
    transitions = ["hard-cut", "whip", "push", "flash"]
    shots = []
    cursor = 0.0
    index = 0
    while cursor < max(8.0, target_seconds):
        beat = beats[index % len(beats)]
        duration = min(durations[index % len(durations)], target_seconds - cursor)
        if duration <= 0:
            break
        shots.append(TimelineShot(
            start=round(cursor, 2),
            duration=round(duration, 2),
            kind=beat.kind,
            subject=beat.subject,
            motion=beat.motion,
            transition=transitions[index % len(transitions)],
        ))
        cursor += duration
        index += 1
    return shots


def timeline_plan(title: str, target_seconds: float = 24.0) -> dict:
    shots = build_video_timeline(title, target_seconds)
    return {
        "mode": "motion-first-editorial-video",
        "target_seconds": target_seconds,
        "shots": [asdict(shot) for shot in shots],
        "max_static_seconds": 0.0,
        "visual_change_every_seconds": 2.2,
        "allow_generic_stock": False,
        "fallback": "animated-branded-editorial-scene",
    }
