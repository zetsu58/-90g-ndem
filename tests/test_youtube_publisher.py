from viral_futbol.publishers.youtube import YouTubePublisher, YouTubeUpload


def test_youtube_dry_run_does_not_require_file():
    result = YouTubePublisher(dry_run=True).publish(
        YouTubeUpload("missing.mp4", "Başlık", "Açıklama")
    )
    assert result.ok is True
    assert result.external_id == "dry-run"


def test_youtube_live_requires_video_file():
    result = YouTubePublisher(dry_run=False).publish(
        YouTubeUpload("missing.mp4", "Başlık", "Açıklama")
    )
    assert result.ok is False
    assert "not found" in result.error
