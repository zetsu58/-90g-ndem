import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from production import remotion_bridge

class RemotionMultiFormatBridgeTests(unittest.TestCase):
    def _asset(self, root:Path, name:str)->Path:
        p=root/name; p.write_bytes(b"asset"); return p

    def test_longform_manifest_and_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); media=self._asset(root,"frame.png"); output=root/"out.mp4"
            captured={}
            def fake_run(cmd,**kwargs):
                manifest=Path(cmd[2]); captured.update(json.loads(manifest.read_text(encoding="utf-8")))
                output.write_bytes(b"\x00\x00\x00\x18ftyp"+b"x"*2048)
                return subprocess.CompletedProcess(cmd,0,"ok","")
            with patch.object(remotion_bridge,"PUBLIC_ROOT",root/"public"), patch("production.remotion_bridge.subprocess.run",side_effect=fake_run) as run:
                ok=remotion_bridge.render(output=output,title="Test",caption="Caption",duration=210,kind="football",media=[media],content_format="video",scenes=[{"start":0,"duration":18,"caption":"A","mediaIndex":0,"section":"hook"}],beats=[{"start":0,"duration":5,"mediaIndex":0,"sceneIndex":0}],captions=[{"text":"merhaba dünya","startMs":0,"endMs":1000,"tokens":[{"text":"merhaba","startMs":0,"endMs":500},{"text":"dünya","startMs":500,"endMs":1000}]}],force=True)
            self.assertTrue(ok)
            self.assertEqual(captured["contentFormat"],"video")
            self.assertEqual(captured["duration"],210)
            self.assertEqual(captured["scenes"][0]["duration"],18)
            self.assertEqual(captured["beats"][0]["duration"],5)
            self.assertEqual(captured["captions"][0]["text"],"merhaba dünya")
            self.assertGreaterEqual(run.call_args.kwargs["timeout"],900)

    def test_short_remains_default(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); media=self._asset(root,"frame.png"); output=root/"out.mp4"; captured={}
            def fake_run(cmd,**kwargs):
                captured.update(json.loads(Path(cmd[2]).read_text(encoding="utf-8")))
                output.write_bytes(b"\x00\x00\x00\x18ftyp"+b"x"*2048)
                return subprocess.CompletedProcess(cmd,0,"ok","")
            with patch.object(remotion_bridge,"PUBLIC_ROOT",root/"public"), patch("production.remotion_bridge.subprocess.run",side_effect=fake_run):
                self.assertTrue(remotion_bridge.render(output=output,title="S",caption="",duration=30,kind="meme",media=[media],force=True))
            self.assertEqual(captured["contentFormat"],"short")

if __name__=="__main__": unittest.main()
