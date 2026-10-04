import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from production.documentary_post import inspect_documentary

class DocumentaryPostTests(unittest.TestCase):
    def test_qc_accepts_dense_visuals_and_mastered_audio(self):
        with tempfile.TemporaryDirectory() as td, \
             patch("production.documentary_post._visual_samples",return_value={"samples":42,"detected_visual_changes":24,"dark_samples":0,"mean_frame_delta":18.2}), \
             patch("production.documentary_post._loudness",return_value={"integrated_lufs":-16.1,"true_peak_dbtp":-1.7,"lra":6.0}):
            report=inspect_documentary(Path(td)/"video.mp4",42,210)
        self.assertTrue(report["passed"])

    def test_qc_rejects_slideshow_like_output(self):
        with tempfile.TemporaryDirectory() as td, \
             patch("production.documentary_post._visual_samples",return_value={"samples":42,"detected_visual_changes":3,"dark_samples":0,"mean_frame_delta":2.1}), \
             patch("production.documentary_post._loudness",return_value={"integrated_lufs":-16.0,"true_peak_dbtp":-1.5,"lra":5.0}):
            with self.assertRaisesRegex(ValueError,"documentary_qc_visual_changes"):
                inspect_documentary(Path(td)/"video.mp4",42,210)

if __name__=="__main__": unittest.main()
