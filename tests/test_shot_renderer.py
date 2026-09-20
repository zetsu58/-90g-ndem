"""Ensure the bounded-memory shot path still yields a vertical MP4."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from viral_futbol.shot_renderer import render_shot, stitch_shots


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class ShotRendererTests(unittest.TestCase):
    def test_two_motion_shots_are_joined_without_xfade_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shots = []
            for index, color in enumerate(('#12572a', '#60212a')):
                image = root / f'{index}.png'
                Image.new('RGB', (720, 1280), color).save(image)
                shot = root / f'{index}.mp4'
                render_shot(image, shot, 0.9, 'slow-push')
                shots.append(shot)
            output = root / 'joined.mp4'
            stitch_shots(shots, output)
            probe = subprocess.run([
                'ffprobe', '-v', 'error', '-show_entries',
                'format=duration:stream=codec_type,width,height', '-of', 'json', str(output),
            ], capture_output=True, text=True, check=True, timeout=10)
            metadata = json.loads(probe.stdout)
            self.assertGreater(float(metadata['format']['duration']), 1.5)
            self.assertEqual((metadata['streams'][0]['width'], metadata['streams'][0]['height']), (1080, 1920))


if __name__ == '__main__':
    unittest.main()
