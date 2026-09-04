from __future__ import annotations

from viral_futbol.config import Settings
from viral_futbol.service import run_scan
from viral_futbol.worker import AutonomousWorker


def cycle() -> object:
    settings = Settings.from_env()
    return run_scan(settings)


if __name__ == "__main__":
    print("ViralFutbol autonomous worker started", flush=True)
    AutonomousWorker(cycle).serve_forever()
