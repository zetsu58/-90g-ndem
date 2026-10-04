import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from production import documentary_media
from viral_futbol import pexels_media
from viral_futbol import youtube_publisher, lite_video


class RelevantMediaTests(unittest.TestCase):
    def _response(self, payload):
        return io.BytesIO(json.dumps(payload).encode("utf-8"))

    def test_short_search_requires_license_resolution_and_whole_subject(self):
        def page(name, license_name="CC BY-SA 4.0", width=1400, height=900):
            return {"title": "File:" + name, "imageinfo": [{
                "mime": "image/jpeg", "width": width, "height": height,
                "thumburl": "https://thumb.wikimedia.org/" + name,
                "extmetadata": {"LicenseShortName": {"value": license_name}},
            }]}
        payload={"query": {"pages": {
            "1": page("Thomas Reis Samsunspor.jpg"),
            "2": page("Thomas The Reis painting.jpg"),
            "3": page("Thomas Reis fan boy.jpg"),
            "4": page("Thomas Reis portrait.jpg", "All rights reserved"),
            "5": page("Thomas Reis tiny.jpg", width=300),
        }}}
        with patch.object(pexels_media.urllib.request, "urlopen", return_value=self._response(payload)):
            found=pexels_media._commons_urls("Thomas Reis")
        self.assertEqual(len(found),1)
        self.assertIn("Samsunspor",found[0]["title"])

    def test_short_rejects_one_repeated_photo(self):
        with tempfile.TemporaryDirectory() as td, patch.object(pexels_media,"_search_relevant",return_value=[{"url":"https://example.com/a.jpg","title":"File:Arda Güler.jpg"}]):
            frames=pexels_media.download_pexels_frames(title="Arda Güler",narration="Arda Güler.",sources=[],output_dir=Path(td),story_id="one")
        self.assertEqual(frames,[])

    def test_landscape_subject_preserved_in_portrait_frame(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/"source.jpg";output=root/"frame.jpg"
            image=Image.new("RGB",(1600,900),(20,40,80))
            for x in range(0,350):
                for y in range(150,750): image.putpixel((x,y),(240,30,30))
            image.save(source)
            pexels_media._render_frame(source,output,"Arda Güler","Kariyerinin başı","CC BY-SA",0,2)
            with Image.open(output) as rendered:
                self.assertEqual(rendered.size,(1080,1920))
                self.assertGreater(rendered.getpixel((140,700))[0],100)

    def test_documentary_search_rejects_partial_subject_and_fans(self):
        def page(name):
            return {"title":"File:"+name,"imageinfo":[{
                "mime":"image/jpeg","width":1600,"height":900,
                "thumburl":"https://thumb.wikimedia.org/"+name,
                "extmetadata":{"LicenseShortName":{"value":"CC BY 4.0"}},
            }]}
        payload={"query":{"pages":{"1":page("Arda Güler Real Madrid.jpg"),
                                      "2":page("Arda football stadium.jpg"),
                                      "3":page("Arda Güler fan boy.jpg")}}}
        with patch.object(documentary_media.urllib.request,"urlopen",return_value=self._response(payload)):
            found=documentary_media._commons("Arda Güler","Arda Güler",6)
        self.assertEqual([x["title"] for x in found],["File:Arda Güler Real Madrid.jpg"])

    def test_lite_render_stops_before_tts_without_relevant_images(self):
        with tempfile.TemporaryDirectory() as td, \
             patch.object(lite_video,"download_pexels_frames",return_value=[]), \
             patch.object(lite_video,"_save_speech") as speech:
            with self.assertRaisesRegex(ValueError,"insufficient_relevant_visual_media"):
                lite_video.render_lite_video(story_id="visual-gate",title="Arda Güler maçı",
                    sources=[],language="tr",voice_name="tr-TR-AhmetNeural",output_dir=td)
            speech.assert_not_called()

    def test_short_description_carries_commons_attribution(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); video=root/"story.mp4";video.write_bytes(b"mp4")
            (root/"story-media-credits.json").write_text(json.dumps([{
                "artist":"Photographer","license":"CC BY-SA 4.0",
                "page":"https://commons.wikimedia.org/wiki/File:Subject.jpg",
            }]),encoding="utf-8")
            credits=youtube_publisher._media_credits({"video_path":video.as_uri()})
        title,description,tags=youtube_publisher._metadata({"title":"Arda Güler transferi","language":"tr","media_credits":credits})
        self.assertIn("Photographer · CC BY-SA 4.0",description)
        self.assertIn("commons.wikimedia.org/wiki/File:Subject.jpg",description)


if __name__=="__main__": unittest.main()
