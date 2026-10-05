"""Timed setup, actual comic action, reaction cut and replay on bounded FFmpeg."""
from __future__ import annotations
import hashlib
import json
import math
import struct
import subprocess
import wave
from pathlib import Path
from .engine import _download, _escape_drawtext_path
from .meme_catalog import CONTRACT


def _sound(path, duration, punchline, reaction):
    """Original, quiet suspense notes + scratch/impact cues; no third-party sound."""
    rate = 24000
    with wave.open(str(path), "wb") as out:
        out.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        data = bytearray()
        for i in range(math.ceil(duration * rate)):
            t = i / rate
            beat = t % .5
            value = .045 * math.exp(-beat * 20) * math.sin(2 * math.pi * 220 * t)
            for at, freq in ((punchline, 120), (reaction, 420)):
                dt = t - at
                if 0 <= dt < .3:
                    value += .35 * math.exp(-dt * 14) * math.sin(2 * math.pi * (freq * dt - 180 * dt * dt))
            data.extend(struct.pack("<h", int(max(-.9, min(.9, value)) * 32767)))
        out.writeframes(data)


def build_reaction_video(clip, output_dir="storage/bamloop", *, local_source=None):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps(clip, sort_keys=True).encode()).hexdigest()[:16]
    output = directory / f"reaction-{key}.mp4"
    source = directory / f"{key}-source.webm"
    pending = directory / f"{key}.pending.mp4"
    scratch = []
    span = clip["end"] - clip["start"]
    reaction_duration = 1.8
    replay_start = max(0, clip["punchline_at"] - 2)
    replay_duration = min(3, span - replay_start)
    total = span + reaction_duration + replay_duration
    metadata = {
        "title": (clip["title"] + " #Shorts")[:100],
        "description": ("#meme #komik #shorts\n\n"
                        f"Kaynak: {clip['author']} — {clip['source_page']}\n"
                        f"Kaynak lisansı: {clip.get('license_name', 'CC BY-SA 4.0')} — {clip['license_url']}\n"
                        f"BAMLOOP katkıları: {clip.get('adaptation_license_name', clip.get('license_name', 'CC BY-SA 4.0'))} — {clip.get('adaptation_license_url', clip['license_url'])}\n"
                        "Değişiklikler: Türkçe espri, kısa kurgu, tepki yakın planı, tekrar ve özgün ses efektleri.\n"
                        "Üretici bu uyarlamayı destekliyor anlamına gelmez."),
        "tags": clip.get("tags", ["meme", "komik", "shorts", "kedi", "tepki"]),
        "meme_contract": CONTRACT, "clip_id": clip["id"],
        "source_sha256": clip["sha256"], "reviewed_event": clip["reviewed_event"],
        "duration_seconds": total, "content_format": "short",
        "edit_beats": ["setup", "real_action", "reaction_closeup", "replay"],
    }
    try:
        if local_source:
            import shutil
            shutil.copyfile(local_source, source)
        else:
            _download(clip["url"], source)
        if hashlib.sha256(source.read_bytes()).hexdigest() != clip["sha256"]:
            raise ValueError("Reviewed source changed; visual re-review required")
        info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)], timeout=30))
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        if video["width"] > 1920 or video["height"] > 1920 or float(info["format"]["duration"]) < clip["end"]:
            raise ValueError("Source dimensions or event timeline exceed reviewed bounds")
        # Process the reviewed action only; never reverse-buffer the source.
        filters = [f"[0:v]trim=duration={span},setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=black,fps=30,format=yuv420p,split=3[main][react][again]",
                   f"[react]trim=start={clip['reaction_at']}:duration=0.1,setpts=PTS-STARTPTS,scale=864:1536,crop=720:1280,tpad=stop_mode=clone:stop_duration={reaction_duration},trim=duration={reaction_duration}[reaction]",
                   f"[again]trim=start={replay_start}:duration={replay_duration},setpts=PTS-STARTPTS[replay]",
                   "[main][reaction][replay]concat=n=3:v=1:a=0[cut]"]
        captions = [(clip["setup"], 0, clip["punchline_at"]),
                    (clip["punchline"], clip["punchline_at"], span),
                    (clip["reaction"], span, span + reaction_duration),
                    (clip["punchline"], span + reaction_duration, total)]
        previous = "cut"
        for i, (text, start, end) in enumerate(captions):
            file = directory / f"{key}-{i}.txt"
            scratch.append(file)
            file.write_text(text, encoding="utf-8")
            following = f"caption{i}"
            filters.append(f"[{previous}]drawtext=expansion=none:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:textfile='{_escape_drawtext_path(file)}':fontcolor=white:fontsize=38:borderw=3:bordercolor=black:box=1:boxcolor=black@0.65:boxborderw=12:x=(w-text_w)/2:y=80:line_spacing=8:enable='gte(t,{start})*lt(t,{end})'[{following}]")
            previous = following
        sound = directory / f"{key}-sound.wav"
        scratch.append(sound)
        _sound(sound, total, clip["punchline_at"], span)
        if clip.get("preserve_source_audio", True) and any(s["codec_type"] == "audio" for s in info["streams"]):
            filters.append(f"[0:a]atrim=duration={span},asetpts=PTS-STARTPTS,apad,atrim=duration={total},volume=0.5[original]")
            filters.append("[original][1:a]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.9[a]")
        else:
            filters.append("[1:a]alimiter=limit=0.9[a]")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-filter_complex_threads", "1", "-threads", "1", "-ss", str(clip["start"]), "-i", str(source), "-i", str(sound), "-filter_complex", ";".join(filters), "-map", f"[{previous}]", "-map", "[a]", "-t", str(total), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-threads", "1", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(pending)], check=True, timeout=180)
        from viral_futbol.youtube_publisher import _validate_short
        _validate_short(pending)
        pending.replace(output)
        return output, metadata
    finally:
        source.unlink(missing_ok=True)
        pending.unlink(missing_ok=True)
        for file in scratch:
            file.unlink(missing_ok=True)
