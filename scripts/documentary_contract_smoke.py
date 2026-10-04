"""Zero-network production contract smoke for the documentary stack."""
from production.longform import plan
from production.documentary_media import visual_beats, _normalize_archive_video
from production.timed_tts import _approximate,_pages
from production.documentary_post import inspect_documentary, master_audio
from production.longform_renderer import render_contract, low_memory_ffmpeg_enabled
import os,subprocess,tempfile
from pathlib import Path
from scripts.run_worker import _force_pair_pending,_mark_force_pair_complete,_short_generated

def main():
    facts=[f"Doğrulanmış olgu {i}" for i in range(12)]
    editorial=plan("Galatasaray",channel="viral_futbol",facts=facts,target_seconds=210)
    scenes=editorial["scenes"]
    assert 8<=len(scenes)<=15, len(scenes)
    assert abs(sum(float(x["duration"]) for x in scenes)-210)<0.5
    beats=visual_beats(scenes,8,5.0)
    assert len(beats)>=40, len(beats)
    for left,right in zip(beats,beats[1:]):
        assert left["mediaIndex"]!=right["mediaIndex"], "adjacent media repeated"
    tokens=_approximate("Bu profesyonel belgesel altyazı zamanlaması için kısa bir örnek cümledir.",5000)
    pages=_pages(tokens)
    assert pages and all(1<=len(x["text"].split())<=7 for x in pages)
    assert callable(inspect_documentary)
    assert callable(render_contract)
    previous_renderer=os.environ.get("LONGFORM_FORCE_FFMPEG")
    os.environ["LONGFORM_FORCE_FFMPEG"]="true"
    try:
        assert low_memory_ffmpeg_enabled()
    finally:
        if previous_renderer is None:
            os.environ.pop("LONGFORM_FORCE_FFMPEG",None)
        else:
            os.environ["LONGFORM_FORCE_FFMPEG"]=previous_renderer
    with tempfile.TemporaryDirectory(prefix="pair-smoke-") as pair_td:
        pair_db=str(Path(pair_td)/"pair.sqlite3")
        previous=os.environ.get("VIRAL_FORCE_PAIR_TOKEN")
        os.environ["VIRAL_FORCE_PAIR_TOKEN"]="smoke-pair-token"
        try:
            assert _force_pair_pending(pair_db)
            assert _short_generated({"generated_lite":1})
            assert not _short_generated({"generated_lite":0,"selected":[]})
            _mark_force_pair_complete(pair_db)
            assert not _force_pair_pending(pair_db)
        finally:
            if previous is None:
                os.environ.pop("VIRAL_FORCE_PAIR_TOKEN",None)
            else:
                os.environ["VIRAL_FORCE_PAIR_TOKEN"]=previous
    with tempfile.TemporaryDirectory(prefix="doc-smoke-") as td:
        sample=Path(td)/"sample.mp4"
        subprocess.run([
            "ffmpeg","-y","-loglevel","error",
            "-f","lavfi","-i","testsrc2=size=640x360:rate=30",
            "-f","lavfi","-i","sine=frequency=440:sample_rate=48000",
            "-t","3","-c:v","libx264","-preset","ultrafast","-crf","20",
            "-c:a","aac","-b:a","160k","-pix_fmt","yuv420p",str(sample)
        ],check=True,timeout=60)
        mastered=master_audio(sample)
        assert mastered["mode"]=="two_pass", mastered
        assert sample.exists() and sample.stat().st_size>100000
        archive=Path(td)/"archive.avi"
        normalized=Path(td)/"archive.mp4"
        subprocess.run([
            "ffmpeg","-y","-loglevel","error","-f","lavfi","-i","testsrc2=size=640x360:rate=24",
            "-t","3","-an","-c:v","mpeg4","-q:v","4",str(archive)
        ],check=True,timeout=60)
        _normalize_archive_video(archive,normalized)
        codec=subprocess.run([
            "ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=codec_name",
            "-of","default=nw=1:nk=1",str(normalized)
        ],capture_output=True,text=True,check=True,timeout=30).stdout.strip()
        assert codec=="h264", codec
    filters=subprocess.run(["ffmpeg","-hide_banner","-filters"],capture_output=True,text=True,check=True).stdout
    encoders=subprocess.run(["ffmpeg","-hide_banner","-encoders"],capture_output=True,text=True,check=True).stdout
    assert "loudnorm" in filters, "ffmpeg loudnorm missing"
    assert "subtitles" in filters, "ffmpeg subtitles/libass missing"
    assert "libx264" in encoders, "ffmpeg libx264 missing"
    print("documentary_contract_smoke=ok")

if __name__=="__main__":
    main()
