from __future__ import annotations

from viral_futbol.config import Settings
from viral_futbol.service import run_scan
from viral_futbol.worker import AutonomousWorker


def cycle() -> object:
    return run_scan(Settings())


if __name__ == "__main__":
    print("ViralFutbol autonomous worker started", flush=True)
    AutonomousWorker(cycle).serve_forever()
