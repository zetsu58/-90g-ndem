from __future__ import annotations

import compileall
import subprocess
import sys


def main() -> int:
    print("[ViralFutbol] compiling package...")
    if not compileall.compile_dir("viral_futbol", quiet=1):
        return 1

    print("[ViralFutbol] running tests...")
    try:
        completed = subprocess.run([sys.executable, "-m", "pytest", "-q"], check=False)
    except FileNotFoundError:
        print("pytest is not installed. Run: python -m pip install pytest")
        return 2
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
