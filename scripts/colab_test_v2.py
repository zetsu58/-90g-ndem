from __future__ import annotations

import compileall
import subprocess
import sys


V2_TESTS = [
    "tests/test_viral_engine.py",
    "tests/test_service_v2_gate.py",
    "tests/test_service_v2_payload.py",
    "tests/test_media_engine.py",
    "tests/test_visual_quality.py",
    "tests/test_retention_engine.py",
]


def run(command: list[str]) -> None:
    print("\n$ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


def main() -> int:
    print("=== Viral Futbol V2 / Colab Test Runner ===")
    if not compileall.compile_dir("viral_futbol", quiet=1):
        print("Python compile kontrolü başarısız.")
        return 1
    run([sys.executable, "-m", "pip", "install", "-q", "pytest"])
    run([sys.executable, "-m", "pytest", "-q", *V2_TESTS])
    print("\nV2 testleri tamamlandı. GitHub Actions kullanılmadı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
