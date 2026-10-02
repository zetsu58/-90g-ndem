import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from production.longform_renderer import render_longform
from production.longform_research import Evidence,build_fact_manifest

def manifest():
    return build_fact_manifest("Bir konu",[
        Evidence("Olgu bir","A"),Evidence("Olgu iki","B"),Evidence("Olgu üç","A"),
        Evidence("Olgu dört","B"),Evidence("Olgu beş","A"),Evidence("Olgu altı","B")])

class LongFormRendererTests(unittest.TestCase):
    def test_requires_narration(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); frame=root/"a.png"; frame.write_bytes(b"x")
            with self.assertRaises(ValueError):
                render_longform(subject="x",channel="bamloop",output=root/"o.mp4",media=[frame],audio=root/"missing.wav",fact_manifest=manifest())

    def test_requires_verified_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); frame=root/"a.png"; frame.write_bytes(b"x"); audio=root/"a.wav"; audio.write_bytes(b"x")
            with self.assertRaises(ValueError):
                render_longform(subject="Bir konu",channel="bamloop",output=root/"o.mp4",media=[frame],audio=audio)

    def test_uses_video_profile(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); frame=root/"a.png"; frame.write_bytes(b"x"); audio=root/"a.wav"; audio.write_bytes(b"x"); out=root/"o.mp4"
            def fake_render(**kwargs):
                out.write_bytes(b"x"*120000); return True
            with patch("production.longform_renderer.render",side_effect=fake_render) as rr, patch("production.longform_renderer._validate_video",return_value={"format":"video"}) as qc:
                result=render_longform(subject="Bir konu",channel="bamloop",output=out,media=[frame],audio=audio,fact_manifest=manifest(),force=True)
            self.assertEqual(rr.call_args.kwargs["content_format"],"video")
            qc.assert_called_once_with(out,"video")
            self.assertEqual(result["metadata"]["content_format"],"video")
            self.assertEqual(result["script_contract"]["evidence_id"],manifest()["id"])

if __name__=="__main__": unittest.main()
