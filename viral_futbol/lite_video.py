from __future__ import annotations

import asyncio
import os
import re
import subprocess
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


def _edge_voice(configured: str, language: str) -> str:
    voice = configured.strip()
    if voice.endswith("-Male") or voice.endswith("-Female"):
        voice = voice.rsplit("-", 1)[0]
    if "Neural" not in voice:
        return "tr-TR-AhmetNeural" if language == "tr" else "en-US-GuyNeural"
    return voice


def build_lite_narration(title: str, sources: list[str], language: str = "tr") -> str:
    clean = re.sub(r"\s+", " ", title).strip().rstrip(".")
    publishers = ", ".join(sources[:3])
    if language == "en":
        source_line = f"The report published by {publishers} describes this development." if publishers else "A recent report describes this development."
        return (
            f"A new development is moving the football agenda: {clean}. "
            f"{source_line} We are summarizing the source without adding "
            "rumours or invented claims. Why could this matter for the club and its supporters? "
            "Follow Viral Futbol for the next verified update, and tell us what you think in the comments."
        )
    source_line = f"Bu gelişme {publishers} kaynağındaki habere dayanıyor." if publishers else "Bu gelişme güncel bir haber kaynağına dayanıyor."
    return (
        f"Futbol gündemini hareketlendiren yeni gelişme: {clean}. "
        f"{source_line} Kaynaktaki bilgiyi özetliyor; "
        "söylenti veya uydurma ayrıntı eklemiyoruz. Bu gelişme kulüp ve taraftarlar için neden önemli olabilir? "
        "Yeni gelişmeler için Viral Futbol'u takip et ve yorumunu yaz."
    )


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _wrapped(text: str, width: int) -> list[str]:
    return wrap(text, width=width, break_long_words=False, break_on_hyphens=False)


def _card(path: Path, title: str, narration: str, sources: list[str]) -> None:
    width, height = 720, 1280
    image = Image.new("RGB", (width, height), "#07111f")
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / height
        draw.line((0, y, width, y), fill=(7 + int(8 * ratio), 17 + int(25 * ratio), 31 + int(35 * ratio)))
    # Branded football visual: stadium lights, pitch, ball and speed lines.
    draw.rectangle((0, 120, width, 690), fill="#0b3d2b")
    for x in range(0, width, 90):
        draw.polygon(((x, 120), (x + 45, 120), (x + 150, 690), (x + 70, 690)), fill="#0f5138")
    draw.arc((90, 270, 630, 850), 185, 355, fill="#d5ffe4", width=7)
    draw.line((360, 420, 360, 690), fill="#d5ffe4", width=6)
    draw.ellipse((278, 458, 442, 622), fill="#f8fafc", outline="#111827", width=8)
    draw.polygon(((360, 480), (397, 507), (383, 553), (337, 553), (323, 507)), fill="#111827")
    for px, py in ((315, 474), (408, 478), (425, 565), (293, 568)):
        draw.ellipse((px - 18, py - 18, px + 18, py + 18), fill="#111827")
    for offset in range(5):
        draw.line((35, 210 + offset * 55, 250, 250 + offset * 55), fill="#38e07b", width=5)
    draw.ellipse((470, 760, 930, 1320), fill="#112d55")

    accent = "#38e07b"
    draw.rounded_rectangle((48, 54, 672, 126), radius=24, fill="#0d241a", outline=accent, width=2)
    draw.text((75, 73), "VİRAL FUTBOL  •  SON DAKİKA", font=_font(27, True), fill=accent)

    y = 190
    title_font = _font(48, True)
    for line in _wrapped(title, 24)[:6]:
        draw.text((52, y), line, font=title_font, fill="white")
        y += 61

    y = 745
    draw.rounded_rectangle((42, y - 25, 678, 1090), radius=30, fill="#0b1727", outline="#38e07b", width=2)
    hook = narration.split(".")[0].strip() + "."
    body_font = _font(34, True)
    for line in _wrapped(hook, 34)[:5]:
        draw.text((70, y), line, font=body_font, fill="#ffffff")
        y += 48
    draw.rounded_rectangle((70, 1015, 250, 1068), radius=18, fill="#38e07b")
    draw.text((95, 1028), "GÜNDEM", font=_font(21, True), fill="#07111f")
    draw.rounded_rectangle((270, 1015, 475, 1068), radius=18, fill="#ffffff")
    draw.text((294, 1028), "HIZLI ÖZET", font=_font(21, True), fill="#07111f")

    source_text = "Kaynak: " + (", ".join(sources[:1]) if sources else "güncel yayın")
    draw.text((52, 1160), source_text[:82], font=_font(20), fill="#9fb1c5")
    draw.text((52, 1205), "#Futbol  #SonDakika  #Shorts", font=_font(24, True), fill=accent)
    image.save(path, "PNG", optimize=True)


async def _save_speech(text: str, voice: str, path: Path) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+16%", pitch="+6Hz")
    await communicate.save(str(path))


def render_lite_video(
    *,
    story_id: str,
    title: str,
    sources: list[str],
    language: str,
    voice_name: str,
    output_dir: str,
) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    final_path = directory / f"{story_id}.mp4"
    if final_path.exists() and final_path.stat().st_size > 1024:
        return final_path

    narration = build_lite_narration(title, sources, language)
    card_path = directory / f"{story_id}.png"
    audio_path = directory / f"{story_id}.mp3"
    _card(card_path, title, narration, sources)
    try:
        asyncio.run(_save_speech(narration, _edge_voice(voice_name, language), audio_path))
    except Exception as exc:
        offline_voice = "tr" if language == "tr" else "en-us"
        print(f"ViralFutbol Edge TTS unavailable, using offline voice: {exc}", flush=True)
        subprocess.run(
            ["espeak-ng", "-v", offline_voice, "-s", "165", "-w", str(audio_path), narration],
            check=True,
            timeout=60,
        )

    command = [
        "ffmpeg", "-y", "-loglevel", "error", "-filter_threads", "1",
        "-loop", "1", "-framerate", "24", "-i", str(card_path),
        "-i", str(audio_path),\n        "-f", "lavfi", "-i", "sine=frequency=110:sample_rate=44100",\n        "-vf", "scale=540:960,format=yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage", "-threads", "1",
        "-filter_complex", "[1:a]volume=1.0[voice];[2:a]tremolo=f=2.2:d=0.7,volume=0.05[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=2[a]",\n        "-map", "0:v", "-map", "[a]",\n        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
        str(final_path),
    ]
    timeout = max(60, int(os.getenv("LITE_VIDEO_TIMEOUT_SECONDS", "180")))
    subprocess.run(command, check=True, timeout=timeout)
    if final_path.stat().st_size < 1024 or b"ftyp" not in final_path.read_bytes()[:64]:
        raise RuntimeError("Lite video engine did not create a valid MP4")
    card_path.unlink(missing_ok=True)
    audio_path.unlink(missing_ok=True)
    return final_path
