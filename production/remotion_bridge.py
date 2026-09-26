from __future__ import annotations
import json, os, shutil, subprocess, tempfile, uuid
from pathlib import Path

REMOTION_ROOT = Path("remotion")
PUBLIC_ROOT = REMOTION_ROOT / "public"

def enabled() -> bool:
    return os.getenv("REMOTION_ENABLED", "false").lower() in {"1", "true", "yes", "on"}

def render(*, output: Path, title: str, caption: str, duration: float, kind: str,
           media: list[Path], audio: Path | None = None, music: Path | None = None) -> bool:
    if not enabled():
        return False
    job_id = uuid.uuid4().hex
    job_dir = PUBLIC_ROOT / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    def stage(source: Path, label: str) -> str:
        suffix = source.suffix.lower() or ".bin"
        target = job_dir / f"{label}{suffix}"
        shutil.copy2(source, target)
        return f"jobs/{job_id}/{target.name}"
    manifest = {"title": title, "caption": caption, "duration": duration, "kind": kind, "media": []}
    for index, source in enumerate(media):
        if source.exists():
            manifest["media"].append(stage(source, f"media-{index}"))
    if audio and audio.exists():
        manifest["audio"] = stage(audio, "voice")
    if music and music.exists():
        manifest["music"] = stage(music, "music")
    fd, name = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    Path(name).write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    try:
        subprocess.run(
            ["node", "remotion/render.mjs", name, str(output)],
            check=True,
            timeout=max(180, int(os.getenv("REMOTION_TIMEOUT_SECONDS", "360"))),
        )
        return output.exists() and output.stat().st_size > 1024 and b"ftyp" in output.read_bytes()[:64]
    except Exception as exc:
        print(f"Remotion render failed; FFmpeg fallback active: {exc}", flush=True)
        output.unlink(missing_ok=True)
        return False
    finally:
        Path(name).unlink(missing_ok=True)
        shutil.rmtree(job_dir, ignore_errors=True)
