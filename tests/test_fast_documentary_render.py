"""The small-instance path must create a real, captioned H.264/AAC documentary."""
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from production.longform_ffmpeg import render_slideshow


def test_fast_documentary_is_real_video_with_audio_and_duration(tmp_path: Path):
    media=[]
    for index,color in enumerate(((170,50,30),(20,100,190))):
        path=tmp_path/f"scene-{index}.jpg"
        Image.new("RGB",(1280,720),color).save(path)
        media.append(path)
    audio=tmp_path/"voice.wav"
    subprocess.run(["ffmpeg","-y","-loglevel","error","-f","lavfi", "-i","sine=frequency=440:duration=8", "-c:a","pcm_s16le",str(audio)],check=True,timeout=20)
    output=tmp_path/"documentary.mp4"
    beats=[{"start":0,"duration":4,"mediaIndex":0},{"start":4,"duration":4,"mediaIndex":1}]
    with patch.dict("os.environ",{"LONGFORM_FAST_FFMPEG":"true"}):
        render_slideshow(media=media,scenes=[{"start":0,"duration":4},{"start":4,"duration":4}],
                         audio=audio,output=output,beats=beats,
                         captions=[{"text":"Fenerbahçe ve Real Madrid","startMs":500,"endMs":2200}])
    probe=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration:stream=codec_name,width,height", "-of","json",str(output)],capture_output=True,text=True,check=True,timeout=20)
    payload=json.loads(probe.stdout)
    assert 7.8 <= float(payload["format"]["duration"]) <= 8.2
    assert [(s["codec_name"],s.get("width"),s.get("height")) for s in payload["streams"]]==[("h264",1280,720),("aac",None,None)]
    assert output.stat().st_size>100000
