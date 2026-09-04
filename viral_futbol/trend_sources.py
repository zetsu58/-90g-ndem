from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class TrendItem:
    title: str
    url: str
    source: str
    published: datetime
    channel: str = "web"
    official: bool = False
    social_velocity: float = 0.0


class TrendSource(Protocol):
    """Adapter boundary for future MCP/API providers such as X, Reddit and YouTube."""

    def fetch(self, query: str) -> list[TrendItem]: ...


class TrendSourceRegistry:
    def __init__(self, sources: tuple[TrendSource, ...] = ()) -> None:
        self.sources = sources

    def fetch_all(self, query: str) -> list[TrendItem]:
        items: list[TrendItem] = []
        for source in self.sources:
            try:
                items.extend(source.fetch(query))
            except Exception as exc:
                print(f"ViralFutbol trend source error: {exc}")
        return items
