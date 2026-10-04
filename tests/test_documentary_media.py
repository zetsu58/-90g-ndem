import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from production.documentary_media import build_documentary_media,visual_beats

class DocumentaryMediaTests(unittest.TestCase):
    def scenes(self):
        return [
            {"start":0.0,"duration":17.5,"section":"hook"},
            {"start":17.5,"duration":17.5,"section":"origins"},
            {"start":35.0,"duration":17.5,"section":"rise"},
            {"start":52.5,"duration":17.5,"section":"turning_points"},
            {"start":70.0,"duration":17.5,"section":"legacy_now"},
            {"start":87.5,"duration":17.5,"section":"outro"},
            {"start":105.0,"duration":17.5,"section":"rise"},
            {"start":122.5,"duration":17.5,"section":"turning_points"},
            {"start":140.0,"duration":17.5,"section":"legacy_now"},
            {"start":157.5,"duration":17.5,"section":"rise"},
            {"start":175.0,"duration":17.5,"section":"turning_points"},
            {"start":192.5,"duration":17.5,"section":"outro"},
        ]

    def test_visual_beats_refresh_documentary_often(self):
        beats=visual_beats(self.scenes(),8,5.0)
        self.assertGreaterEqual(len(beats),40)
        self.assertAlmostEqual(sum(x["duration"] for x in beats),210.0,places=1)
        self.assertTrue(all(3.5<=x["duration"]<=7.0 for x in beats))
        for left,right in zip(beats,beats[1:]):
            self.assertNotEqual(left["mediaIndex"],right["mediaIndex"])

    def test_real_media_gate_fails_closed_instead_of_text_cards(self):
        with tempfile.TemporaryDirectory() as td, patch("production.documentary_media._commons",return_value=[]), patch("production.documentary_media._pexels",return_value=[]):
            with self.assertRaisesRegex(ValueError,"documentary_real_media_gate"):
                build_documentary_media(subject="Örnek Futbolcu",scenes=self.scenes(),claims=["Doğrulanmış olgu"],output_dir=Path(td),content_id="abc",channel="viral_futbol",target_assets=12)

    def test_motion_broll_gate_rejects_photo_only_documentary(self):
        items=[{"url":f"https://example.test/{i}.jpg","title":"Örnek Futbolcu","source":"Wikimedia Commons","license":"CC BY","artist":"","page":""} for i in range(10)]
        def fake_download(url,path,max_bytes):
            Path(path).write_bytes(b"raw")
        def fake_clean(source,destination):
            Path(destination).write_bytes(b"image")
        fingerprints=iter([f"fp{i}" for i in range(20)])
        with tempfile.TemporaryDirectory() as td, \
             patch.dict("os.environ",{"LONGFORM_MIN_REAL_MEDIA":"8","LONGFORM_MIN_VIDEO_BROLL":"2"},clear=False), \
             patch("production.documentary_media._commons",return_value=items), \
             patch("production.documentary_media._pexels",return_value=[]), \
             patch("production.documentary_media._download",side_effect=fake_download), \
             patch("production.documentary_media._clean_image",side_effect=fake_clean), \
             patch("production.documentary_media._image_fingerprint",side_effect=lambda path: next(fingerprints)):
            with self.assertRaisesRegex(ValueError,"documentary_motion_media_gate"):
                build_documentary_media(subject="Örnek Futbolcu",scenes=self.scenes(),claims=["Doğrulanmış olgu"],output_dir=Path(td),content_id="abc",channel="viral_futbol",target_assets=12)

if __name__=="__main__": unittest.main()
