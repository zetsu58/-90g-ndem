"""Original, lightweight vehicle suspension simulations for BAMLOOP Shorts.

The scene is illustrative rather than a claim about real vehicle safety.
No game recording, car logo, or third-party footage is used.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CONTRACT = "original-vehicle-simulation-v1"
SCENARIOS = tuple(
    {"id": f"bump-{speed}-{height}", "speed": speed, "bump": height}
    for speed in (35, 55, 75, 95) for height in (8, 14, 20)
)
VEHICLES = (
    ("HAFİF", "#20d6e3", .76, 1.15),
    ("SUV", "#ffbc4b", 1.22, .78),
    ("SPOR", "#eb5e86", 1.04, .58),
)
W, H, FPS = 720, 1280, 24
DURATION = 13.0


def scenario_id(scenario: dict) -> str:
    return hashlib.sha256((CONTRACT + "|" + scenario["id"]).encode()).hexdigest()[:24]


def scenario_signature(scenario: dict) -> str:
    return hashlib.sha256(json.dumps(scenario, sort_keys=True).encode()).hexdigest()


def _font(size: int) -> ImageFont.FreeTypeFont:
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    return ImageFont.truetype(path, size) if Path(path).exists() else ImageFont.load_default()


def _label(draw: ImageDraw.ImageDraw, text: str, y: int, size: int, fill: str = "white") -> None:
    font = _font(size)
    bounds = draw.textbbox((0, 0), text, font=font)
    draw.text(((W - bounds[2] + bounds[0]) / 2, y), text, font=font, fill=fill, stroke_width=2, stroke_fill="#0b1327")


def _tone(path: Path) -> None:
    rate = 24000
    with wave.open(str(path), "wb") as sound:
        sound.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        chunk = bytearray()
        for n in range(int(DURATION * rate)):
            t = n / rate
            pulse = 0.0
            for at in (3.11, 6.91, 10.71):
                dt = t - at
                if 0 <= dt < .28:
                    pulse += .28 * math.exp(-dt * 19) * math.sin(2 * math.pi * (135 * dt - 120 * dt * dt))
            pulse += .018 * math.sin(2 * math.pi * 70 * t) * (1 if t % .5 < .12 else 0)
            chunk.extend(struct.pack("<h", round(max(-.8, min(.8, pulse)) * 32767)))
        sound.writeframes(chunk)


def _frame(t: float, scenario: dict) -> Image.Image:
    image = Image.new("RGB", (W, H), "#101b37")
    d = ImageDraw.Draw(image)
    # Vertical editorial composition: readable figures, road, and a result card.
    d.rectangle((0, 0, W, 155), fill="#0a1229")
    _label(d, "BAMLOOP  /  SIMÜLASYON", 27, 31, "#85eafa")
    _label(d, f"{scenario['speed']} KM/SA  •  {scenario['bump']} CM TÜMSEK", 84, 29)
    d.rounded_rectangle((27, 174, 693, 272), 18, fill="#263657")
    _label(d, "3 ARAÇ, AYNI ENGEL", 189, 40)
    _label(d, "Sence hangisi daha az zıplar?", 241, 20, "#c8d7ec")

    if t >= 12.1:
        scores = sorted((round(scenario["bump"] * 2.0 * (scenario["speed"] / 55) ** .7 * suspension / mass), name, color)
                        for name, color, mass, suspension in VEHICLES)
        _label(d, "SONUÇ / EN AZ ZIPLAYAN", 360, 35, "#85eafa")
        _label(d, scores[0][1], 505, 76, scores[0][2])
        for place, (score, name, color) in enumerate(scores, 1):
            d.rounded_rectangle((58, 681 + place * 100, 662, 756 + place * 100), 18, fill="#263657")
            _label(d, f"{place}. {name}  /  {score} BİRİM", 693 + place * 100, 29, color)
        _label(d, "Aynı engel, farklı tepki", 1177, 24, "#d1dbe7")
        return image

    index = min(2, max(0, int(max(0, t - .7) / 3.8)))
    segment_t = max(0, t - .7 - index * 3.8)
    name, color, mass, suspension = VEHICLES[index]
    _label(d, f"{index + 1}/3  •  {name}", 311, 38, color)

    road_y = 799
    d.rectangle((0, 388, W, road_y), fill="#344c68")
    d.polygon([(0, 388), (190, 322), (355, 386), (565, 332), (720, 389)], fill="#4c6c7f")
    d.rectangle((0, road_y, W, 941), fill="#222c3e")
    d.line((0, road_y, W, road_y), fill="#f0e3a8", width=7)
    shift = (segment_t * scenario["speed"] * 5) % 210
    for x in range(-210, W + 210, 210):
        d.rounded_rectangle((x - shift, 865, x + 92 - shift, 875), 4, fill="#d0d9df")
    # Obstacle translates with the road, while camera tracks the car.
    bump_x = 1035 - segment_t * 315
    bump_h = scenario["bump"] * 3.1
    d.polygon([(bump_x - 62, road_y), (bump_x - 17, road_y - bump_h),
               (bump_x + 17, road_y - bump_h), (bump_x + 62, road_y)], fill="#e1a645")
    d.line((bump_x - 61, road_y - 4, bump_x - 17, road_y - bump_h + 3,
            bump_x + 17, road_y - bump_h + 3, bump_x + 60, road_y - 4), fill="#fff0aa", width=5)
    impact_at = (1035 - 276) / 315
    after = max(0.0, segment_t - impact_at)
    amplitude = scenario["bump"] * 2.0 * (scenario["speed"] / 55) ** .7 * suspension / mass
    bounce = amplitude * math.exp(-after * 2.5) * abs(math.sin(after * 12.5)) if after else 0
    x, body_y = 276, road_y - 65 - bounce
    d.ellipse((x - 171, road_y - 15, x + 159, road_y + 18), fill="#162039")
    d.rounded_rectangle((x - 157, body_y - 45, x + 157, body_y + 22), 23, fill=color, outline="#f7fcff", width=3)
    d.polygon([(x - 74, body_y - 44), (x - 38, body_y - 99), (x + 78, body_y - 99),
               (x + 120, body_y - 43)], fill=color)
    d.polygon([(x - 57, body_y - 50), (x - 28, body_y - 85), (x + 65, body_y - 85),
               (x + 91, body_y - 50)], fill="#a9dfea")
    for wx in (x - 100, x + 100):
        d.ellipse((wx - 28, body_y, wx + 28, body_y + 56), fill="#0a1021", outline="#f1f2f7", width=4)
        d.ellipse((wx - 8, body_y + 19, wx + 8, body_y + 37), fill="#859aaa")
    if 0 < after < .24:
        for j in range(7):
            px = x + 108 + j * 13
            py = road_y - 40 - ((j * 17) % 43)
            d.ellipse((px, py, px + 7, py + 7), fill="#ffe3a1")
    d.rounded_rectangle((28, 956, 692, 1130), 23, fill="#1a2a47", outline="#567590", width=2)
    if after:
        _label(d, f"TAHMİNİ ZIPLAMA: {round(amplitude)} BİRİM", 981, 28, "#ffe6a6")
        _label(d, "Etki: " + ("YÜKSEK" if amplitude > 55 else "ORTA" if amplitude > 34 else "DÜŞÜK"), 1042, 34, color)
    else:
        _label(d, "ENGELE YAKLAŞIYOR", 1000, 35, color)
        _label(d, "Temsili süspansiyon modeli", 1057, 23, "#d1dbe7")
    _label(d, "ÖZGÜN GRAFİK • TEMSİLİ FİZİK", 1191, 18, "#a9b9d0")
    return image


def build_simulation_video(scenario: dict, output_dir: str = "storage/bamloop"):
    if scenario not in SCENARIOS:
        raise ValueError("Unknown simulation scenario")
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"simulation-{scenario['id']}.mp4"
    pending = directory / f"simulation-{scenario['id']}.pending.mp4"
    sound = directory / f"simulation-{scenario['id']}.wav"
    _tone(sound)
    args = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
            "-r", str(FPS), "-i", "pipe:0", "-i", str(sound), "-c:v", "libx264", "-preset", "ultrafast",
            "-crf", "24", "-threads", "1", "-c:a", "aac", "-b:a", "96k", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-shortest", str(pending)]
    try:
        with subprocess.Popen(args, stdin=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
            try:
                for n in range(round(DURATION * FPS)):
                    proc.stdin.write(_frame(n / FPS, scenario).tobytes())
                proc.stdin.close()
                error = proc.stderr.read()
                if proc.wait(timeout=180):
                    raise RuntimeError("Simulation render failed: " + error.decode(errors="replace")[-600:])
            except Exception:
                proc.kill()
                proc.wait()
                raise
        from viral_futbol.youtube_publisher import _validate_short
        _validate_short(pending)
        pending.replace(output)
    finally:
        pending.unlink(missing_ok=True)
        sound.unlink(missing_ok=True)
    metadata = {
        "title": f"{scenario['speed']} km/sa hız tümseği: 3 araç simülasyonu #Shorts",
        "description": "Özgün grafiklerle hazırlanmış temsili araç/süspansiyon simülasyonu. "
                       "Sonuçlar gerçek araç testi, güvenlik ölçümü veya sürüş önerisi değildir. "
                       "#simülasyon #otomobil #shorts",
        "tags": ["simülasyon", "otomobil", "hız tümseği", "shorts"],
        "meme_contract": CONTRACT, "simulation_id": scenario["id"],
        "simulation_signature": scenario_signature(scenario),
        "content_format": "short", "duration_seconds": DURATION,
    }
    return output, metadata
