from unittest.mock import patch

import pytest

from viral_futbol.youtube_publisher import _safe_upload_error, _validate_short


@pytest.mark.parametrize("width,height,accepted", [(720, 1280, True), (720, 1400, False), (640, 1138, False)])
def test_publish_gate_requires_vertical_720p_and_nine_sixteen(tmp_path, monkeypatch, width, height, accepted):
    monkeypatch.delenv("SHORTS_MIN_WIDTH", raising=False)
    monkeypatch.delenv("SHORTS_MIN_HEIGHT", raising=False)
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\0\0\0\x18ftyp" + b"\0" * 100_000)
    metadata = {"format": {"duration": "25"}, "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": width, "height": height},
        {"codec_type": "audio", "codec_name": "aac"},
    ]}
    with patch("viral_futbol.youtube_publisher._probe", return_value=metadata):
        if accepted:
            assert _validate_short(video)["width"] == 720
        else:
            with pytest.raises(ValueError, match="Quality gate"):
                _validate_short(video)


def test_upload_error_reports_only_safe_http_reason():
    class ProviderError(Exception):
        resp = type('Response', (), {'status': 403})()
        content = b'{"error":{"errors":[{"reason":"quotaExceeded","message":"refresh_token=private"}]}}'

    assert _safe_upload_error(ProviderError()) == 'YouTubeHTTP403_quotaExceeded'
