"""Zero-network production contract smoke for the documentary stack."""
from production.longform import plan
from production.documentary_media import visual_beats
from production.timed_tts import _approximate,_pages
from production.documentary_post import inspect_documentary
from production.longform_renderer import render_contract

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
    print("documentary_contract_smoke=ok")

if __name__=="__main__":
    main()
