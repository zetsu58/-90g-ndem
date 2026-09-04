from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PublishResult:
    ok: bool
    provider: str
    external_id: str = ""
    url: str = ""
    error: str = ""


class Publisher(Protocol):
    def publish(self, *args, **kwargs) -> PublishResult: ...
