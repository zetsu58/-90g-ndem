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

def beats():
    return [{"start":i*5.0,"duration":5.0,"mediaIndex":i%8,"sceneIndex":i//3} for i in range(42)]

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

    def test_passes_documentary_beats_to_remotion(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); media=[]
            for i in range(8):
                frame=root/f"{i}.png";frame.write_bytes(b"x");media.append(frame)
            audio=root/"a.wav";audio.write_bytes(b"x");out=root/"o.mp4"
            def fake_render(**kwargs):
                out.write_bytes(b"x"*120000);return True
            with patch("production.longform_renderer.render",side_effect=fake_render) as rr, patch("production.longform_renderer._validate_video",return_value={"format":"video"}) as qc:
                result=render_longform(subject="Bir konu",channel="bamloop",output=out,media=media,audio=audio,fact_manifest=manifest(),force=True,visual_beats=beats())
            self.assertEqual(rr.call_args.kwargs["content_format"],"video")
            self.assertEqual(len(rr.call_args.kwargs["beats"]),42)
            self.assertLessEqual(len(rr.call_args.kwargs["scenes"][0]["caption"].split()),18)
            qc.assert_called_once_with(out,"video")
            self.assertEqual(result["visual_beat_count"],42)

    def test_ffmpeg_fallback_receives_documentary_beats(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); media=[]
            for i in range(8):
                frame=root/f"{i}.png";frame.write_bytes(b"x");media.append(frame)
            audio=root/"a.wav";audio.write_bytes(b"x");out=root/"o.mp4"
            def fake_ffmpeg(**kwargs):
                out.write_bytes(b"x"*120000)
            timeline=beats()
            with patch("production.longform_renderer.render",return_value=False), patch("production.longform_renderer.render_slideshow",side_effect=fake_ffmpeg) as ff, patch("production.longform_renderer._validate_video",return_value={"format":"video"}):
                result=render_longform(subject="Bir konu",channel="bamloop",output=out,media=media,audio=audio,fact_manifest=manifest(),visual_beats=timeline)
            self.assertEqual(result["renderer"],"ffmpeg")
            self.assertEqual(ff.call_args.kwargs["beats"],timeline)

if __name__=="__main__": unittest.main()
