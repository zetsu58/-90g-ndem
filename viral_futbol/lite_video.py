from __future__ import annotations

import asyncio
import os
import re
import subprocess
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont

from .pexels_media import download_pexels_frames
from .creative_learning import recommended_hook
from .video_timeline import timeline_plan
from .shot_renderer import render_shot, stitch_shots
from .creative_store import remember_creative
from production.music import instrumental
from production.remotion_bridge import render as render_remotion


def _edge_voice(configured: str, language: str) -> str:
    voice = configured.strip()
    if voice.endswith("-Male") or voice.endswith("-Female"):
        voice = voice.rsplit("-", 1)[0]
    if "Neural" not in voice:
        return "tr-TR-AhmetNeural" if language == "tr" else "en-US-GuyNeural"
    return voice


def build_lite_narration(
    title: str,
    sources: list[str],
    language: str = "tr",
    hook: str | None = None,
    facts: list[str] | None = None,
) -> str:
    del sources
    clean = re.sub(r"\s+", " ", title).strip().rstrip(".")
    clean_facts: list[str] = []
    seen = {clean.casefold()}
    for fact in facts or []:
        value = re.sub(r"\s+", " ", fact).strip().rstrip(".")
        key = value.casefold()
        if value and key not in seen:
            clean_facts.append(value)
            seen.add(key)
    detail = ". ".join(clean_facts[:3])
    if language == "en":
        verified = f" {detail}." if detail else ""
        return f"Football update: {clean}.{verified} Follow 90 Plus Gundem for the next update."
    # Put the news in the first breath. Never pad sparse reports with invented
    # consequences or claims of an official announcement.
    lead = clean if clean.endswith(("?", "!")) else f"{clean}."
    details = [fact for fact in clean_facts if fact.casefold() not in clean.casefold()]
    body = " ".join(f"{fact}." for fact in details[:2])
    ending = "Gelişmeler geldikçe aktaracağız. 90+ Gündem'de takipte kalın."
    return " ".join(part for part in (lead, body, ending) if part)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    for candidate in candidates:
        if Path(candidate).exists(): return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _wrapped(text: str, width: int) -> list[str]:
    return wrap(text, width=width, break_long_words=False, break_on_hyphens=False)


def _card(path: Path, title: str, narration: str, sources: list[str], variant: int = 0) -> None:
    width, height = 720, 1280
    image = Image.new("RGB", (width, height), "#07111f"); draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / height; draw.line((0, y, width, y), fill=(7 + int(8 * ratio), 17 + int(25 * ratio), 31 + int(35 * ratio)))
    draw.rectangle((0, 120, width, 690), fill="#0b3d2b")
    for x in range(0, width, 90): draw.polygon(((x, 120), (x + 45, 120), (x + 150, 690), (x + 70, 690)), fill="#0f5138")
    draw.arc((90, 270, 630, 850), 185, 355, fill="#d5ffe4", width=7); draw.line((360, 420, 360, 690), fill="#d5ffe4", width=6)
    draw.ellipse((278, 458, 442, 622), fill="#f8fafc", outline="#111827", width=8); draw.polygon(((360, 480), (397, 507), (383, 553), (337, 553), (323, 507)), fill="#111827")
    for px, py in ((315, 474), (408, 478), (425, 565), (293, 568)): draw.ellipse((px - 18, py - 18, px + 18, py + 18), fill="#111827")
    for offset in range(5): draw.line((35 + 13 * variant, 210 + offset * 55, 250 + 13 * variant, 250 + offset * 55), fill="#ff2438", width=5)
    draw.ellipse((470, 760, 930, 1320), fill="#112d55"); accent = "#ff2438"; draw.rounded_rectangle((38, 38, 682, 140), radius=24, fill="#050505", outline=accent, width=3)
    logo_path = Path(__file__).resolve().parents[1] / "assets" / "90gundem-logo-v2.png"
    if logo_path.exists():
        try:
            with Image.open(logo_path) as logo_opened:
                logo = logo_opened.convert("RGBA"); logo.thumbnail((88, 88), Image.Resampling.LANCZOS)
            image.paste(logo, (55, 45), logo); draw = ImageDraw.Draw(image)
        except (OSError, ValueError):
            # Damaged optional branding must not prevent timely news production.
            print("ViralFutbol optional logo unavailable", flush=True)
    draw.text((160, 72), "FUTBOL HABERİ  •  90+ GÜNDEM", font=_font(23, True), fill="white")
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


def _media_duration(path: Path, fallback: float = 24.0) -> float:
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
            check=True, capture_output=True, text=True, timeout=20,
        )
        return max(8.0, min(70.0, float(probe.stdout.strip())))
    except Exception:
        return fallback


def render_lite_video(*, story_id: str, title: str, sources: list[str], facts: list[str] | None = None, language: str, voice_name: str, output_dir: str) -> Path:
    directory = Path(output_dir); directory.mkdir(parents=True, exist_ok=True); final_path = directory / f"{story_id}.mp4"
    if final_path.exists() and final_path.stat().st_size > 1024: return final_path
    hook = None
    try:
        db_path = (os.getenv("NEWS_DB_PATH", "") or os.getenv("DB_PATH", "")).strip()
        if db_path:
            hook = recommended_hook(db_path)
    except Exception as exc:
        print(f"ViralFutbol hook learning deferred: {exc}", flush=True)
    narration = build_lite_narration(title, sources, language, hook, facts)
    if db_path:
        remember_creative(db_path, story_id, hook)
    card_path = directory / f"{story_id}.png"; audio_path = directory / f"{story_id}.mp3"
    frames = download_pexels_frames(title=title, narration=narration, sources=sources, output_dir=directory, story_id=story_id)
    # Editorial graphics are honest when relevant licensed imagery is absent.
    # Never substitute footage of an unrelated player or club.
    if not frames:
        beats = [title, *(facts or [])]
        for index in range(3):
            frame = directory / f"{story_id}-editorial-{index}.png"
            _card(frame, beats[index % len(beats)], narration, sources, index)
            frames.append(frame)
    try: asyncio.run(_save_speech(narration, _edge_voice(voice_name, language), audio_path))
    except Exception as exc:
        offline_voice = "tr" if language == "tr" else "en-us"; print(f"ViralFutbol Edge TTS unavailable, using offline voice: {exc}", flush=True); subprocess.run(["espeak-ng", "-v", offline_voice, "-s", "175", "-w", str(audio_path), narration], check=True, timeout=60)
    audio_duration = _media_duration(audio_path)
    # A terse breaking story can be voiced in under twelve seconds. Hold the
    # final editorial beat and music rather than discarding a fresh story.
    target_duration = max(13.0, min(70.0, audio_duration + 0.35))
    timeline = timeline_plan(title, target_duration)
    shot_paths = []
    motion_video = None
    if frames:
        for index, shot in enumerate(timeline["shots"]):
            shot_path = directory / f"{story_id}-shot-{index}.mp4"
            render_shot(frames[index % len(frames)], shot_path, float(shot["duration"]), str(shot["motion"]))
            shot_paths.append(shot_path)
        motion_video = directory / f"{story_id}-motion.mp4"
        stitch_shots(shot_paths, motion_video, [str(shot["transition"]) for shot in timeline["shots"]], [float(shot["duration"]) for shot in timeline["shots"]])
        concat_path = None
        video_input = ["-i", str(motion_video)]
    else:
        concat_path = None
        video_input = ["-loop", "1", "-framerate", "24", "-i", str(card_path)]
    if motion_video:
        video_filter = "scale=1080:1920:flags=lanczos,eq=contrast=1.04:saturation=1.06,fade=t=in:st=0:d=0.10,fps=30,format=yuv420p"
    else:
        video_filter = "scale=1350:2400:flags=lanczos,crop=1080:1920:x='135+82*sin(t*0.82)+27*sin(t*2.1)':y='240+105*cos(t*0.61)+24*sin(t*1.7)',eq=contrast=1.06:saturation=1.08,fade=t=in:st=0:d=0.10,fps=30,format=yuv420p"
    try:
        music_volume = float(os.getenv("SHORTS_MUSIC_VOLUME", "0.20"))
    except ValueError:
        music_volume = 0.20
    music_volume = max(0.05, min(0.35, music_volume))
    mix = f"[1:a]volume=1.20,acompressor=threshold=0.14:ratio=2.7:attack=4:release=90,apad,asplit=2[side][voice];[2:a]highpass=f=55,lowpass=f=9000,volume={music_volume}[bed];[bed][side]sidechaincompress=threshold=0.035:ratio=8:attack=12:release=280[ducked];[voice][ducked]amix=inputs=2:duration=first:dropout_transition=1:normalize=0,alimiter=limit=0.94[a]"
    music_value = os.getenv("SHORTS_MUSIC_FILE", "").strip()
    music_path = Path(music_value) if music_value else None
    if music_path and music_path.is_file():
        music_input = ["-stream_loop", "-1", "-i", str(music_path)]
    else:
        music_input = ["-stream_loop", "-1", "-i", str(instrumental(directory / "original-bed.wav"))]
    remotion_media = [Path(frame) for frame in frames]\n    if render_remotion(output=final_path, title=title, caption=narration.split(".")[0], duration=target_duration, kind="football", media=remotion_media, audio=audio_path, music=music_path if music_path and music_path.is_file() else None):\n        command = None\n    else:\n        command = ["ffmpeg", "-y", "-loglevel", "error", "-filter_threads", "1", *video_input, "-i", str(audio_path), *music_input, "-vf", video_filter, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-threads", "1", "-filter_complex", mix, "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-t", f"{target_duration:.2f}", "-shortest", "-movflags", "+faststart", str(final_path)]
    try:
        timeout = max(60, int(os.getenv("LITE_VIDEO_TIMEOUT_SECONDS", "180")))
    except ValueError:
        timeout = 180
    if command is not None:\n        subprocess.run(command, check=True, timeout=timeout)
    if final_path.stat().st_size < 1024 or b"ftyp" not in final_path.read_bytes()[:64]: raise RuntimeError("Lite video engine did not create a valid MP4")
    card_path.unlink(missing_ok=True); audio_path.unlink(missing_ok=True)
    if concat_path: concat_path.unlink(missing_ok=True)
    for frame in frames: frame.unlink(missing_ok=True)
    for shot_path in shot_paths: shot_path.unlink(missing_ok=True)
    if motion_video: motion_video.unlink(missing_ok=True)
    return final_path
