from __future__ import annotations
import json, os, shutil, subprocess, tempfile, uuid
from pathlib import Path

REMOTION_ROOT = Path("remotion")
PUBLIC_ROOT = REMOTION_ROOT / "public"

def enabled() -> bool:
    return os.getenv("REMOTION_ENABLED", "false").lower() in {"1", "true", "yes", "on"}

def render(*, output: Path, title: str, caption: str, duration: float, kind: str,
           media: list[Path], audio: Path | None = None, music: Path | None = None, content_format: str = "short", force: bool = False, timeout_seconds: int | None = None, diagnostic: dict | None = None) -> bool:
    if not (force or enabled()):
        return False
    job_id = uuid.uuid4().hex
    job_dir = PUBLIC_ROOT / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    def stage(source: Path, label: str) -> str:
        suffix = source.suffix.lower() or ".bin"
        target = job_dir / f"{label}{suffix}"
        shutil.copy2(source, target)
        return f"jobs/{job_id}/{target.name}"
    manifest = {"title": title, "caption": caption, "duration": duration, "kind": kind, "contentFormat": content_format, "smoke": kind == "smoke", "media": []}
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
        completed = subprocess.run(
            ["node", "remotion/render.mjs", name, str(output)],
            check=True, capture_output=True, text=True,
            timeout=max(10, timeout_seconds if timeout_seconds is not None else int(os.getenv("REMOTION_LONGFORM_TIMEOUT_SECONDS" if content_format == "video" else "REMOTION_TIMEOUT_SECONDS", "900" if content_format == "video" else "360"))),
        )
        if diagnostic is not None:
            diagnostic["stdout"] = (completed.stdout or "")[-1000:]
            diagnostic["stderr"] = (completed.stderr or "")[-1000:]
        return output.exists() and output.stat().st_size > 1024 and b"ftyp" in output.read_bytes()[:64]
    except Exception as exc:
        if diagnostic is not None:
            diagnostic["error"] = type(exc).__name__
            diagnostic["detail"] = str(exc)[-500:]
            diagnostic["stdout"] = (getattr(exc, "stdout", "") or "")[-1000:]
            diagnostic["stderr"] = (getattr(exc, "stderr", "") or "")[-1000:]
        print(f"Remotion render failed; FFmpeg fallback active: {type(exc).__name__}: {exc}", flush=True)
        output.unlink(missing_ok=True)
        return False
    finally:
        Path(name).unlink(missing_ok=True)
        shutil.rmtree(job_dir, ignore_errors=True)
