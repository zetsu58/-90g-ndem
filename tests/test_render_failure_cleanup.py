"""A crashed final FFmpeg must never leave a publishable cache entry."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from viral_futbol.lite_video import render_lite_video


def test_final_ffmpeg_failure_does_not_cache_partial_mp4(tmp_path):
    frame = tmp_path / 'frame.png'
    Image.new('RGB', (720, 1280), '#234567').save(frame)

    async def speech(_text, _voice, path):
        Path(path).write_bytes(b'fixture-audio')

    def interrupted(command, **_kwargs):
        Path(command[-1]).write_bytes(b'ftyp' + b'partial' * 400)
        raise subprocess.TimeoutExpired(command, 1)

    with patch('viral_futbol.lite_video.download_pexels_frames', return_value=[frame]), \
         patch('viral_futbol.lite_video._save_speech', side_effect=speech), \
         patch('viral_futbol.lite_video._media_duration', return_value=13), \
         patch('viral_futbol.lite_video.render_shot'), \
         patch('viral_futbol.lite_video.stitch_shots'), \
         patch('viral_futbol.lite_video.render_remotion', return_value=False), \
         patch('viral_futbol.lite_video.subprocess.run', side_effect=interrupted):
        with pytest.raises(subprocess.TimeoutExpired):
            render_lite_video(story_id='interrupted', title='Fixture football title', sources=[],
                              language='tr', voice_name='tr-TR-EmelNeural', output_dir=str(tmp_path))
    assert not (tmp_path / 'interrupted.mp4').exists()
    assert not (tmp_path / 'interrupted.pending.mp4').exists()
