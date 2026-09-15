from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisualQualityPlan:
    clip_duration: int
    transition_mode: str
    hook_priority: tuple[str, ...]
    max_repeat_per_term: int
    min_unique_terms: int


def build_visual_quality_plan(media_entities: tuple[str, ...], context: str) -> VisualQualityPlan:
    """Define fast Shorts pacing while avoiding repetitive generic B-roll."""
    primary = media_entities[:2]
    if primary:
        hook = tuple(f"{entity} football close up" for entity in primary)
    elif context == "match":
        hook = ("football stadium crowd close up",)
    else:
        hook = ("football breaking news stadium",)
    return VisualQualityPlan(
        clip_duration=3,
        transition_mode="Shuffle",
        hook_priority=hook,
        max_repeat_per_term=1,
        min_unique_terms=4,
    )


def prioritized_terms(base_terms: list[str], plan: VisualQualityPlan) -> list[str]:
    """Put recognisable subject visuals first and keep search terms unique."""
    ordered = [*plan.hook_priority, *base_terms]
    result: list[str] = []
    seen: set[str] = set()
    for term in ordered:
        key = term.casefold().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(term.strip())
    return result
