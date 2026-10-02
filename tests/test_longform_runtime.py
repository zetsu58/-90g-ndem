import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from production.longform_research import Evidence
from production.longform_runtime import produce_once,last_activity
from production.queue import PublishQueue

class LongFormRuntimeTests(unittest.TestCase):
    def evidence(self):
        return [Evidence(f"Olgu {i}","Kaynak A" if i%2 else "Kaynak B") for i in range(12)]
    def fake_media(self,**kwargs):
        root=Path(kwargs["output_dir"]);frames=[]
        for i in range(3):
            p=root/f"f{i}.jpg";p.write_bytes(b"x");frames.append(p)
        return frames,[]
    def fake_tts(self,text,path,voice):
        Path(path).write_bytes(b"x"*2048);return Path(path)
    def fake_music(self,path,*args,**kwargs):
        Path(path).write_bytes(b"x"*12000);return Path(path)
    def fake_render(self,contract,output,force=False):
        Path(output).write_bytes(b"x"*120000)
        return {"renderer":"mock","quality":{"format":"video","duration":210}}
    def test_viral_runtime_queues_file_uri_video(self):
        with tempfile.TemporaryDirectory() as td, patch.dict("os.environ",{"PUBLISH_DIRECT_ENABLED":"true"},clear=False), patch("production.longform_runtime.research",return_value=self.evidence()), patch("production.longform_runtime.generate_narration",return_value={"text":"x "*500,"word_count":500,"provider":"mock"}), patch("production.longform_runtime.build_media",side_effect=self.fake_media), patch("production.longform_runtime.synthesize",side_effect=self.fake_tts), patch("production.longform_runtime.instrumental",side_effect=self.fake_music), patch("production.longform_runtime.render_contract",side_effect=self.fake_render):
            db=str(Path(td)/"v.sqlite3")
            result=produce_once(channel="viral_futbol",db_path=db,output_dir=str(Path(td)/"out"))
            self.assertTrue(result["queued"])
            with PublishQueue(db,"viral_futbol") as q:
                row=q.recent(1)[0]
            self.assertTrue(row["video_path"].startswith("file://"))
            self.assertEqual(json.loads(row["metadata"])["content_format"],"video")
            self.assertIsNotNone(last_activity(db,"viral_futbol"))
    def test_bamloop_runtime_queues_local_path(self):
        with tempfile.TemporaryDirectory() as td, patch.dict("os.environ",{"PUBLISH_DIRECT_ENABLED":"true"},clear=False), patch("production.longform_runtime.research",return_value=self.evidence()), patch("production.longform_runtime.generate_narration",return_value={"text":"x "*500,"word_count":500,"provider":"mock"}), patch("production.longform_runtime.build_media",side_effect=self.fake_media), patch("production.longform_runtime.synthesize",side_effect=self.fake_tts), patch("production.longform_runtime.instrumental",side_effect=self.fake_music), patch("production.longform_runtime.render_contract",side_effect=self.fake_render):
            db=str(Path(td)/"b.sqlite3")
            result=produce_once(channel="bamloop",db_path=db,output_dir=str(Path(td)/"out"))
            self.assertTrue(result["queued"])
            with PublishQueue(db,"bamloop") as q:
                row=q.recent(1)[0]
            self.assertFalse(row["video_path"].startswith("file://"))

if __name__=="__main__": unittest.main()
