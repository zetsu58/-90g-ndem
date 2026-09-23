"""Conservative scene-level creative recommendations for the next render."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from .scene_performance import ScenePerformanceStore


@dataclass(frozen=True)
class SceneCreativeAdvice:
    kind: str
    motion: str
    transition: str
    samples: int
    avg_score: float

    def as_dict(self): return asdict(self)


def recommended_scene_creative(db_path: str, minimum_samples: int = 3) -> SceneCreativeAdvice | None:
    with ScenePerformanceStore(db_path) as store:
        rows=store.leaders(10)
    eligible=[r for r in rows if int(r.get("samples",0)) >= minimum_samples]
    if not eligible: return None
    best=max(eligible,key=lambda r:(float(r.get("avg_score",0)),int(r.get("samples",0))))
    return SceneCreativeAdvice(
        kind=str(best["kind"]), motion=str(best["motion"]), transition=str(best["transition"]),
        samples=int(best["samples"]), avg_score=round(float(best["avg_score"]),2)
    )
