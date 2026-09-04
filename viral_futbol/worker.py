from __future__ import annotations

import os
import signal
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class WorkerConfig:
    interval_seconds: int = 180
    error_backoff_seconds: int = 30

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        return cls(
            interval_seconds=max(30, int(os.getenv("NEWS_WORKER_INTERVAL_SECONDS", "180"))),
            error_backoff_seconds=max(5, int(os.getenv("NEWS_WORKER_ERROR_BACKOFF_SECONDS", "30"))),
        )


class AutonomousWorker:
    def __init__(self, run_once: Callable[[], object], config: WorkerConfig | None = None) -> None:
        self.run_once = run_once
        self.config = config or WorkerConfig.from_env()
        self._running = True

    def stop(self, *_args: object) -> None:
        self._running = False

    def serve_forever(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        while self._running:
            started = time.monotonic()
            try:
                self.run_once()
                delay = max(1.0, self.config.interval_seconds - (time.monotonic() - started))
            except Exception as exc:
                print(f"ViralFutbol worker cycle failed: {exc}", flush=True)
                delay = self.config.error_backoff_seconds
            deadline = time.monotonic() + delay
            while self._running and time.monotonic() < deadline:
                time.sleep(min(1.0, deadline - time.monotonic()))
