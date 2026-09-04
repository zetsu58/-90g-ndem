from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RenderJob:
    story_id: str
    script_path: str
    output_path: str


class VideoWorker:
    """Long-running server worker boundary replacing Colab lifecycle coupling.

    NEWS_RENDER_COMMAND is intentionally configurable. During migration it can
    call MoneyPrinterTurbo; later it can point to the native FFmpeg renderer.
    """

    def __init__(self, command: str | None = None, *, timeout: int | None = None) -> None:
        self.command = (command or os.getenv("NEWS_RENDER_COMMAND", "")).strip()
        self.timeout = timeout or int(os.getenv("NEWS_RENDER_TIMEOUT", "900"))

    def render(self, job: RenderJob) -> str:
        if not self.command:
            raise RuntimeError("NEWS_RENDER_COMMAND is not configured")
        script = Path(job.script_path)
        if not script.is_file():
            raise RuntimeError(f"Render script input not found: {script}")
        output = Path(job.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        command = self.command.format(
            story_id=job.story_id,
            script_path=str(script),
            output_path=str(output),
        )
        completed = subprocess.run(command, shell=True, timeout=self.timeout, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"Video render failed with exit code {completed.returncode}")
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError("Video renderer returned without a valid output file")
        return str(output)
