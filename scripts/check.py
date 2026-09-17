from __future__ import annotations

import compileall
import subprocess
import sys


def main() -> int:
    print("[ViralFutbol] compiling package...")
    if not compileall.compile_dir("viral_futbol", quiet=1):
        return 1

    print("[ViralFutbol] running tests...")
    completed = subprocess.run([sys.executable, "-m", "pytest", "-q"], check=False)
    if completed.returncode:
        return completed.returncode

    print("[ViralFutbol] running offline release smoke gate...")
    smoke = subprocess.run([sys.executable, "scripts/release_smoke.py"], check=False)
    return smoke.returncode


if __name__ == "__main__":
    raise SystemExit(main())
