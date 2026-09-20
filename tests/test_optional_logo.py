"""Damaged optional branding must not block a Shorts render."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from viral_futbol import lite_video, pexels_media


class OptionalLogoTests(unittest.TestCase):
    def test_fallback_card_survives_corrupt_logo(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            assets = root / 'assets'
            assets.mkdir()
            (assets / '90gundem-logo-v2.png').write_bytes(b'not a PNG')
            output = root / 'card.png'
            with patch.object(lite_video, '__file__', str(root / 'viral_futbol' / 'lite_video.py')):
                lite_video._card(output, 'Galatasaray haber', 'Galatasaray haber.', [], 0)
            with Image.open(output) as image:
                self.assertEqual(image.size, (720, 1280))

    def test_relevant_frame_survives_corrupt_logo(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            assets = root / 'assets'
            assets.mkdir()
            (assets / '90gundem-logo-v2.png').write_bytes(b'not a PNG')
            original = root / 'original.png'
            Image.new('RGB', (800, 1000), '#154633').save(original)
            output = root / 'frame.jpg'
            with patch.object(pexels_media, '__file__', str(root / 'viral_futbol' / 'pexels_media.py')):
                pexels_media._render_frame(original, output, 'Galatasaray haber', 'Gelişme', '', 0, 1)
            with Image.open(output) as image:
                self.assertEqual(image.size, (1080, 1920))


if __name__ == '__main__':
    unittest.main()
