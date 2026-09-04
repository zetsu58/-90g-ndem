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
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
