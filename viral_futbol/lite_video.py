from __future__ import annotations

import asyncio
import os
import re
import subprocess
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont

from .pexels_media import download_pexels_frames


def _edge_voice(configured: str, language: str) -> str:
    voice = configured.strip()
    if voice.endswith("-Male") or voice.endswith("-Female"):
        voice = voice.rsplit("-", 1)[0]
    if "Neural" not in voice:
        return "tr-TR-AhmetNeural" if language == "tr" else "en-US-GuyNeural"
    return voice


def build_lite_narration(title: str, sources: list[str], language: str = "tr") -> str:
    del sources
    clean = re.sub(r"\s+", " ", title).strip().rstrip(".")
    if language == "en":
        return f"Wait—this just changed the football agenda: {clean}. Here is what matters in seconds. Watch the next move closely. What do you think happens now? Follow 90 Plus Gundem for the next update."
    return f"Bir saniye—futbol gündemi şimdi değişti: {clean}. Olayın kritik kısmı şu; bundan sonraki hamle her şeyi değiştirebilir. Gözler şimdi yeni gelişmede. Sence sırada ne var? Yorumunu yaz, 90+ Gündem'i takip et."


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    for candidate in candidates:
        if Path(candidate).exists(): return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _wrapped(text: str, width: int) -> list[str]:
    return wrap(text, width=width, break_long_words=False, break_on_hyphens=False)


def _card(path: Path, title: str, narration: str, sources: list[str]) -> None:
    width, height = 720, 1280
    image = Image.new("RGB", (width, height), "#07111f"); draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / height; draw.line((0, y, width, y), fill=(7 + int(8 * ratio), 17 + int(25 * ratio), 31 + int(35 * ratio)))
    draw.rectangle((0, 120, width, 690), fill="#0b3d2b")
    for x in range(0, width, 90): draw.polygon(((x, 120), (x + 45, 120), (x + 150, 690), (x + 70, 690)), fill="#0f5138")
    draw.arc((90, 270, 630, 850), 185, 355, fill="#d5ffe4", width=7); draw.line((360, 420, 360, 690), fill="#d5ffe4", width=6)
    draw.ellipse((278, 458, 442, 622), fill="#f8fafc", outline="#111827", width=8); draw.polygon(((360, 480), (397, 507), (383, 553), (337, 553), (323, 507)), fill="#111827")
    for px, py in ((315, 474), (408, 478), (425, 565), (293, 568)): draw.ellipse((px - 18, py - 18, px + 18, py + 18), fill="#111827")
    for offset in range(5): draw.line((35, 210 + offset * 55, 250, 250 + offset * 55), fill="#ff2438", width=5)
    draw.ellipse((470, 760, 930, 1320), fill="#112d55"); accent = "#ff2438"; draw.rounded_rectangle((38, 38, 682, 140), radius=24, fill="#050505", outline=accent, width=3)
    logo_path = Path(__file__).resolve().parents[1] / "assets" / "90gundem-logo-v2.png"
    if logo_path.exists():
        with Image.open(logo_path) as logo_opened:
            logo = logo_opened.convert("RGBA"); logo.thumbnail((88, 88), Image.Resampling.LANCZOS)
        image.paste(logo, (55, 45), logo); draw = ImageDraw.Draw(image)
    draw.text((160, 72), "SON DAKİKA  •  90+ GÜNDEM", font=_font(25, True), fill="white")
    y = 190; title_font = _font(42, True)
    for line in _wrapped(title, 24)[:6]: draw.text((52, y), line, font=title_font, fill="white"); y += 61
    y = 745; draw.rounded_rectangle((42, y - 25, 678, 1090), radius=30, fill="#0b1727", outline="#ff2438", width=2); hook = narration.split(".")[0].strip() + "."; body_font = _font(29, True)
    for line in _wrapped(hook, 31)[:5]: draw.text((70, y), line, font=body_font, fill="#ffffff"); y += 48
    draw.rounded_rectangle((70, 1015, 250, 1068), radius=18, fill="#ff2438"); draw.text((95, 1028), "GÜNDEM", font=_font(21, True), fill="#07111f"); draw.rounded_rectangle((270, 1015, 475, 1068), radius=18, fill="#ffffff"); draw.text((294, 1028), "HIZLI ÖZET", font=_font(21, True), fill="#07111f")
    draw.text((52, 1160), "90+ Gündem  •  Futbolun nabzı", font=_font(22, True), fill="#e7edf4"); draw.text((52, 1205), "#Futbol  #SonDakika  #Shorts", font=_font(24, True), fill=accent); image.save(path, "PNG", optimize=True)


async def _save_speech(text: str, voice: str, path: Path) -> None:
    import edge_tts
    rate = os.getenv("SHORTS_TTS_RATE", "+32%")
    pitch = os.getenv("SHORTS_TTS_PITCH", "+8Hz")
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch, volume="+15%")
    await communicate.save(str(path))


def render_lite_video(*, story_id: str, title: str, sources: list[str], language: str, voice_name: str, output_dir: str) -> Path:
    directory = Path(output_dir); directory.mkdir(parents=True, exist_ok=True); final_path = directory / f"{story_id}.mp4"
    if final_path.exists() and final_path.stat().st_size > 1024: return final_path
    narration = build_lite_narration(title, sources, language); card_path = directory / f"{story_id}.png"; audio_path = directory / f"{story_id}.mp3"
    frames = download_pexels_frames(title=title, narration=narration, sources=sources, output_dir=directory, story_id=story_id)
    if not frames: _card(card_path, title, narration, sources)
    try: asyncio.run(_save_speech(narration, _edge_voice(voice_name, language), audio_path))
    except Exception as exc:
        offline_voice = "tr" if language == "tr" else "en-us"; print(f"ViralFutbol Edge TTS unavailable, using offline voice: {exc}", flush=True); subprocess.run(["espeak-ng", "-v", offline_voice, "-s", "175", "-w", str(audio_path), narration], check=True, timeout=60)
    if frames:
        concat_path = directory / f"{story_id}-frames.txt"; sequence = [frames[index % len(frames)] for index in range(10)]; rows = []
        for frame in sequence: rows.extend((f"file '{frame.resolve()}'", "duration 1.65"))
        rows.append(f"file '{sequence[-1].resolve()}'"); concat_path.write_text("\n".join(rows) + "\n", encoding="utf-8"); video_input = ["-f", "concat", "-safe", "0", "-i", str(concat_path)]
    else: concat_path = None; video_input = ["-loop", "1", "-framerate", "24", "-i", str(card_path)]
    video_filter = "scale=820:1458:flags=lanczos,crop=720:1280:x='50+28*sin(t*1.05)':y='89+34*cos(t*0.8)',fade=t=in:st=0:d=0.12,fps=30,format=yuv420p"
    music_volume = max(0.05, min(0.35, float(os.getenv("SHORTS_MUSIC_VOLUME", "0.20"))))
    mix = f"[1:a]volume=1.24,acompressor=threshold=0.15:ratio=2.5:attack=5:release=80[voice];[2:a]highpass=f=45,lowpass=f=1600,tremolo=f=4.5:d=0.75,acompressor=threshold=0.2:ratio=3:attack=5:release=80,volume={music_volume}[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=1:normalize=0,alimiter=limit=0.95[a]"
    command = ["ffmpeg", "-y", "-loglevel", "error", "-filter_threads", "1", *video_input, "-i", str(audio_path), "-f", "lavfi", "-i", "aevalsrc=0.30*sin(2*PI*55*t)+0.12*sin(2*PI*110*t)+0.08*sin(2*PI*165*t):s=44100", "-vf", video_filter, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-threads", "1", "-filter_complex", mix, "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(final_path)]
    timeout = max(60, int(os.getenv("LITE_VIDEO_TIMEOUT_SECONDS", "180"))); subprocess.run(command, check=True, timeout=timeout)
    if final_path.stat().st_size < 1024 or b"ftyp" not in final_path.read_bytes()[:64]: raise RuntimeError("Lite video engine did not create a valid MP4")
    card_path.unlink(missing_ok=True); audio_path.unlink(missing_ok=True)
    if concat_path: concat_path.unlink(missing_ok=True)
    for frame in frames: frame.unlink(missing_ok=True)
    return final_path
