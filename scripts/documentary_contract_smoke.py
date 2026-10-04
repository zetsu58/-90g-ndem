"""Zero-network production contract smoke for the documentary stack."""
from production.longform import plan
from production.documentary_media import visual_beats
from production.timed_tts import _approximate,_pages
from production.documentary_post import inspect_documentary
from production.longform_renderer import render_contract
import subprocess

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
    filters=subprocess.run(["ffmpeg","-hide_banner","-filters"],capture_output=True,text=True,check=True).stdout
    encoders=subprocess.run(["ffmpeg","-hide_banner","-encoders"],capture_output=True,text=True,check=True).stdout
    assert "loudnorm" in filters, "ffmpeg loudnorm missing"
    assert "subtitles" in filters, "ffmpeg subtitles/libass missing"
    assert "libx264" in encoders, "ffmpeg libx264 missing"
    print("documentary_contract_smoke=ok")

if __name__=="__main__":
    main()
