"""A terse voiceover must still pass the production MP4 quality gate."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from viral_futbol.lite_video import render_lite_video
from viral_futbol.youtube_publisher import _validate_short


class LiteShortDurationTests(unittest.TestCase):
    def test_short_voiceover_renders_publishable_video(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            # A prior crashed FFmpeg process must not become a cache hit.
            (base / 'short-voice.mp4').write_bytes(b'ftyp' + b'broken' * 400)

            async def speech(_text, _voice, path):
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi',
                                '-i', 'sine=frequency=440:duration=7', '-c:a', 'libmp3lame',
                                str(path)], check=True, timeout=30)

            def frames(**_kwargs):
                frame = base / 'frame.jpg'
                Image.new('RGB', (720, 1280), '#314453').save(frame)
                second = base / 'frame-two.jpg'
                Image.new('RGB', (720, 1280), '#526475').save(second)
                return [frame, second]

            with patch('viral_futbol.lite_video.download_pexels_frames', side_effect=frames), \
                    patch('viral_futbol.lite_video._save_speech', side_effect=speech):
                video = render_lite_video(story_id='short-voice', title='Kulüp açıklama yaptı',
                                          sources=['Kulüp'], facts=[], language='tr',
                                          voice_name='tr-TR-EmelNeural', output_dir=str(base))
            result = _validate_short(video)
            self.assertGreaterEqual(result['duration'], 12)
            # The low-memory production renderer deliberately outputs 720p.
            self.assertEqual((result['width'], result['height']), (720, 1280))


if __name__ == '__main__':
    unittest.main()
