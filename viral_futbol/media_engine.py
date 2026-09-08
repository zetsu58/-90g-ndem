from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class MediaPlan:
    entities: tuple[str, ...]
    queries: tuple[str, ...]
    context: str


KNOWN_ENTITIES = (
    "Galatasaray", "Fenerbahçe", "Beşiktaş", "Trabzonspor",
    "Real Madrid", "Barcelona", "Liverpool", "Manchester City",
    "Bayern Munich", "PSG", "Juventus", "Inter", "Milan",
    "Osimhen", "Icardi", "Salah", "Mbappe", "Haaland", "Yamal",
)


def _context(text: str) -> str:
    lowered = text.casefold()
    if any(x in lowered for x in ("transfer", "bonservis", "kiralık", "imza", "görüşme")):
        return "transfer"
    if any(x in lowered for x in ("sakat", "ameliyat", "tedavi")):
        return "injury"
    if any(x in lowered for x in ("derbi", "maç", "final")):
        return "match"
    return "news"


def build_media_plan(title: str, facts: list[str]) -> MediaPlan:
    """Create contextual stock/B-roll searches without fabricating event footage."""
    text = " ".join([title, *facts])
    entities = tuple(entity for entity in KNOWN_ENTITIES if entity.casefold() in text.casefold())
    context = _context(text)

    subject = " ".join(entities[:2]).strip() or "football"
    if context == "transfer":
        suffixes = ("football transfer", "football player arrival", "football stadium", "football fans")
    elif context == "injury":
        suffixes = ("football player training", "football medical", "football stadium", "football fans")
    elif context == "match":
        suffixes = ("football match stadium", "football fans", "football training", "football goal celebration")
    else:
        suffixes = ("football stadium", "football training", "football fans", "football press conference")

    queries = tuple(dict.fromkeys(f"{subject} {suffix}".strip() for suffix in suffixes))
    return MediaPlan(entities=entities, queries=queries, context=context)


def material_terms(plan: MediaPlan, *, limit: int = 5) -> list[str]:
    return [re.sub(r"\s+", " ", query).strip() for query in plan.queries[:limit]]
