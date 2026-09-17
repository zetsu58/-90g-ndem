from __future__ import annotations

from dataclasses import dataclass

from .pexels_media import _entities, _normalized


@dataclass(frozen=True)
class VisualBeat:
    kind: str
    subject: str
    motion: str
    emphasis: str


def build_visual_beats(title: str) -> list[VisualBeat]:
    entities = _entities(title)
    primary = entities[0] if entities else title
    text = _normalized(title)
    beats = [
        VisualBeat("hero", primary, "slow-push", "headline"),
        VisualBeat("context", primary, "parallax", "identity"),
    ]
    if any(token in text for token in ("transfer", "imza", "bonservis", "kiralik")):
        beats.extend([
            VisualBeat("transfer", primary, "whip-pan", "deal"),
            VisualBeat("detail", primary, "micro-zoom", "status"),
        ])
    elif any(token in text for token in ("mac", "derbi", "gol")):
        beats.extend([
            VisualBeat("match", primary, "punch-in", "event"),
            VisualBeat("score-context", primary, "slide", "impact"),
        ])
    else:
        beats.extend([
            VisualBeat("evidence", primary, "crop-pan", "fact"),
            VisualBeat("recap", primary, "slow-push", "summary"),
        ])
    return beats


def visual_plan(title: str) -> dict:
    beats = build_visual_beats(title)
    return {
        "style": "premium-editorial",
        "stock_footage": False,
        "entity_locked": True,
        "beats": [beat.__dict__ for beat in beats],
        "rules": [
            "never use unrelated generic football footage",
            "prefer entity-matched licensed editorial imagery",
            "use branded motion graphics when exact media is unavailable",
            "do not imply an image depicts the reported event unless verified",
        ],
    }
