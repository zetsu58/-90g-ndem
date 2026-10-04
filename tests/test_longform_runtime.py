import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from production.longform_research import Evidence
from production.longform_runtime import produce_once,last_activity
from production.queue import PublishQueue

class LongFormRuntimeTests(unittest.TestCase):
    def evidence(self):
        return [Evidence(f"Olgu {i}","Kaynak A" if i%2 else "Kaynak B") for i in range(12)]

    def fake_documentary(self,**kwargs):
        root=Path(kwargs["output_dir"]);media=[]
        for i in range(8):
            p=root/f"f{i}.jpg";p.write_bytes(b"x");media.append(p)
        return {"media":media,"credits":[],"report":{"real_media":8,"images":8,"videos":0,"text_cards":0}}

    def fake_tts(self,text,path,voice):
        Path(path).write_bytes(b"x"*2048);return Path(path)

    def fake_music(self,path,*args,**kwargs):
        Path(path).write_bytes(b"x"*12000);return Path(path)

    def fake_render(self,contract,output,force=False):
        self.assertGreaterEqual(len(contract["visual_beats"]),35)
        self.assertEqual(contract["media_report"]["text_cards"],0)
        Path(output).write_bytes(b"x"*120000)
        return {"renderer":"mock","quality":{"format":"video","duration":210}}

    def _patches(self):
        return (
            patch("production.longform_runtime.research",return_value=self.evidence()),
            patch("production.longform_runtime.generate_narration",return_value={"text":"x "*500,"word_count":500,"provider":"mock"}),
            patch("production.longform_runtime.build_documentary_media",side_effect=self.fake_documentary),
            patch("production.longform_runtime.synthesize",side_effect=self.fake_tts),
            patch("production.longform_runtime.instrumental",side_effect=self.fake_music),
            patch("production.longform_runtime.render_contract",side_effect=self.fake_render),
        )

    def test_viral_runtime_queues_documentary_video(self):
        with tempfile.TemporaryDirectory() as td, patch.dict("os.environ",{"PUBLISH_DIRECT_ENABLED":"true"},clear=False):
            a,b,c,d,e,g=self._patches()
            with a,b,c,d,e,g:
                db=str(Path(td)/"v.sqlite3")
                result=produce_once(channel="viral_futbol",db_path=db,output_dir=str(Path(td)/"out"))
            self.assertTrue(result["queued"])
            self.assertGreaterEqual(result["visual_beat_count"],35)
            self.assertEqual(result["documentary_media"]["text_cards"],0)
            with PublishQueue(db,"viral_futbol") as q:
                row=q.recent(1)[0]
            metadata=json.loads(row["metadata"])
            self.assertTrue(row["video_path"].startswith("file://"))
            self.assertEqual(metadata["content_format"],"video")
            self.assertGreaterEqual(metadata["visual_beat_count"],35)
            self.assertEqual(metadata["documentary_media"]["text_cards"],0)
            self.assertIsNotNone(last_activity(db,"viral_futbol"))

    def test_bamloop_runtime_queues_documentary_video(self):
        with tempfile.TemporaryDirectory() as td, patch.dict("os.environ",{"PUBLISH_DIRECT_ENABLED":"true"},clear=False):
            a,b,c,d,e,g=self._patches()
            with a,b,c,d,e,g:
                db=str(Path(td)/"b.sqlite3")
                result=produce_once(channel="bamloop",db_path=db,output_dir=str(Path(td)/"out"))
            self.assertTrue(result["queued"])
            with PublishQueue(db,"bamloop") as q:
                row=q.recent(1)[0]
            self.assertFalse(row["video_path"].startswith("file://"))

if __name__=="__main__": unittest.main()
