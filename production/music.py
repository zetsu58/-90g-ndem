"""Original, deterministic instrumental bed; no external music licensing needed."""
from __future__ import annotations
import math
import struct
import wave
from pathlib import Path


def instrumental(path: Path, seconds: int = 40, sample_rate: int = 22050) -> Path:
    if path.exists() and path.stat().st_size > 10000: return path
    path.parent.mkdir(parents=True, exist_ok=True)
    bpm=112
    beat=60/bpm
    chords=((220,261.63,329.63),(196,246.94,293.66),(174.61,220,261.63),(196,246.94,392))
    with wave.open(str(path),'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(sample_rate)
        for block in range(math.ceil(seconds*sample_rate/4096)):
            samples=[]
            for i in range(block*4096,min((block+1)*4096,seconds*sample_rate)):
                t=i/sample_rate
                phase=t%beat
                chord=chords[int(t/(beat*4))%4]
                pad=sum(math.sin(2*math.pi*f*t)*0.10 for f in chord)
                kick=0.31*math.sin(2*math.pi*(62+55*math.exp(-phase*24))*phase)*math.exp(-phase*19)
                snare_phase=(t-beat)% (2*beat)
                noise=math.sin(i*78.233)*math.sin(i*1.231)
                snare=0.13*noise*math.exp(-snare_phase*42) if snare_phase<.15 else 0
                hat_phase=t%(beat/2)
                hat=0.045*noise*math.exp(-hat_phase*95)
                amplitude=max(-.84,min(.84,pad+kick+snare+hat))
                samples.append(int(amplitude*32767))
            output.writeframes(struct.pack('<'+'h'*len(samples),*samples))
    return path
