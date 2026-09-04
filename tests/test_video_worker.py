import pytest

from viral_futbol.video_worker import RenderJob, VideoWorker


def test_video_worker_requires_command(tmp_path):
    script = tmp_path / "script.txt"
    script.write_text("haber", encoding="utf-8")
    worker = VideoWorker(command="")
    with pytest.raises(RuntimeError, match="NEWS_RENDER_COMMAND"):
        worker.render(RenderJob("1", str(script), str(tmp_path / "out.mp4")))


def test_video_worker_requires_input(tmp_path):
    worker = VideoWorker(command="echo ok")
    with pytest.raises(RuntimeError, match="input not found"):
        worker.render(RenderJob("1", str(tmp_path / "missing.txt"), str(tmp_path / "out.mp4")))
