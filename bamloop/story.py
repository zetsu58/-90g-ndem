"""Original short stories with provider boundaries and a local motion-video fallback."""
from __future__ import annotations

import hashlib
import os
import random
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw, ImageFont

from viral_futbol.youtube_publisher import _validate_short
from production.music import instrumental


@dataclass(frozen=True)
class Scene:
    subject: str
    action: str
    environment: str
    camera: str
    shot_type: str
    movement: str
    lighting: str
    mood: str
    vertical_composition: str
    continuity_context: str
    negative_constraints: str
    narration: str


@dataclass(frozen=True)
class Story:
    idea: str
    scenes: tuple[Scene, ...]


class StoryProvider(Protocol):
    def create(self, seed: str) -> Story: ...


class ImageProvider(Protocol):
    def render(self, scene: Scene, destination: Path, index: int) -> None: ...


class VideoProvider(Protocol):
    def render(self, scenes: tuple[Scene, ...], destination: Path) -> None: ...


PREMISES = (
    ('Bahçedeki küçük robot', 'kaybolan sulama kabını aradı', 'kendi gölgesini bir hırsız sandı', 'gölgesini takip ederken çiçekleri suladı', 'bahçedeki tüm çiçekler açtı'),
    ('Mahalle kedisi', 'kapının önündeki gizemli kutuyu gördü', 'kutudan gelen sese kulak verdi', 'içinden çıkan minik oyuncağı takip etti', 'oyuncak onu sahibinin yanına götürdü'),
    ('Minyatür aşçı', 'dev bir limonun yanında uyandı', 'limonu yuvarlamaya çalıştı', 'arkadaşlarıyla küçük bir rampa kurdu', 'limon herkese yetecek bir limonataya dönüştü'),
    ('Komşunun akıllı süpürgesi', 'mutfakta bir kaşığı kaybetti', 'kaşığın izini bütün evde sürdü', 'masa altındaki mıknatısı buldu', 'kaşıklar tek bir yerde toplandı'),
    ('Küçük bahçıvan', 'gece parlayan bir fide buldu', 'fidenin ışığını takip etti', 'toprağın altında saklı minik bir kapı gördü', 'kapının ardında rengârenk bir bahçe vardı'),
    ('Yağmurdan kaçan ördek', 'boş bir şemsiye buldu', 'şemsiyeyi açınca rüzgâr yükseldi', 'onu küçük bir göletin üstüne taşıdı', 'arkadaşlarıyla birlikte gölete indi'),
    ('Tamirci kirpi', 'kırık saatin tik taklarını duydu', 'dişlileri tek tek inceledi', 'eksik parçayı cebindeki düğmede buldu', 'saat yeniden çalışınca herkes dans etti'),
    ('Minik astronot', 'odasında kırmızı bir düğme buldu', 'düğmeye basınca yıldızlar belirdi', 'yıldızlardan biri masaya kondu', 'meğer odadaki gece lambasıymış'),
    ('Unutkan ressam', 'duvarında hareketli bir iz gördü', 'iz için renkli bir harita çizdi', 'harita onu pencereye çıkardı', 'iz yalnızca sabah güneşinin oyunuymuş'),
    ('Evdeki küçük drone', 'saksıların arasından bir ses duydu', 'kamerasını çiçeklere çevirdi', 'yaprakların arasında bir arı buldu', 'arı açık pencereyi bulup çıktı'),
    ('Sokak köpeği', 'parlayan bir topun peşinden koştu', 'top her köşede yön değiştirdi', 'topun arkasındaki ipi fark etti', 'çocuklarla yepyeni bir oyun başladı'),
    ('Küçük mucit', 'mutfak masasındaki kırıntıları gördü', 'kırıntı toplayan bir makine yaptı', 'makine ekmeği de taşımaya başladı', 'sonunda herkes için kahvaltı hazırladı'),
)


class LocalStoryProvider:
    def create(self, seed: str) -> Story:
        subject, hook, setup, escalation, payoff = random.Random(seed).choice(PREMISES)
        actions = (hook, setup, escalation, payoff)
        narrations = (
            f'{subject} bugün {hook}. Ama burada tuhaf bir şey vardı.',
            f'Önce {setup}. Neler olacağını anlamaya çalışıyordu.',
            f'Tam o sırada {escalation}. İşler iyice değişti.',
            f'Sonunda {payoff}. Bu sürprizi kim beklerdi?',
        )
        scenes = tuple(Scene(subject, action, 'renkli, özgün bir minyatür mahalle',
          'alçak açı, sinematik perspektif', 'yakın plan' if i == 0 else 'orta plan',
          ('push-in','pan','parallax','pull-out')[i], 'sıcak gün ışığı',
          ('şaşkın','meraklı','heyecanlı','neşeli')[i], 'dikey 9:16, yüz merkezde',
          f'aynı {subject}, aynı renk paleti, aynı çevre',
          'yazı yok, logo yok, şiddet yok, watermark yok', narrations[i]) for i, action in enumerate(actions))
        return Story(f'{subject}: {hook} ({random.Random(seed + str(len(seed))).choice(("güneşli gün","akşamüstü","hafta sonu","sabah"))})', scenes)


class LocalImageProvider:
    """Original procedural art; never fetches arbitrary unrelated stock."""
    def render(self, scene: Scene, destination: Path, index: int) -> None:
        rng = random.Random(f'{scene.subject}|{scene.action}|{index}')
        image = Image.new('RGB', (1080,1920), '#101b2b')
        draw = ImageDraw.Draw(image)
        palette = ('#f67362','#f5ba55','#60c6b4','#b38ee7')
        color = palette[index % len(palette)]
        for y in range(1920):
            draw.line((0,y,1080,y), fill=(14 + y//180, 27 + y//160, 44 + y//140))
        for j in range(16):
            x = (j*297 + index*101) % 1080
            y = (j*193 + index*31) % 1600
            radius = 18 + j % 5 * 15
            draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill='#25364b')
        # Layered original scene: horizon, ground, depth objects and a stable hero silhouette.
        draw.rectangle((0,1120,1080,1920), fill='#172b2b')
        for j in range(9):
            x=rng.randint(-80,1000); h=rng.randint(130,420); w=rng.randint(90,230)
            draw.rounded_rectangle((x,1120-h,x+w,1120),radius=18,fill=('#26384a','#304a43','#3d4055')[j%3])
            draw.rectangle((x+w//3,1120-h+45,x+2*w//3,1120-h+95),fill='#ffd67a')
        draw.ellipse((145,365,935,1165), fill=color, outline='#ffffff', width=8)
        draw.ellipse((300,640,420,760),fill='#0b1523')
        draw.ellipse((660,640,780,760),fill='#0b1523')
        draw.arc((390,790,690,940),0,180,fill='#0b1523',width=18)
        # Consistent accessories make the subject recognizable across scenes.
        draw.rounded_rectangle((405,1030,675,1125),radius=28,fill='#e8edf2',outline='#0b1523',width=8)
        draw.ellipse((495,1050,585,1140),fill=color,outline='#0b1523',width=7)
        draw.rounded_rectangle((60,1410,1020,1770),radius=40,fill='#07121f',outline=color,width=7)
        font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
        font=ImageFont.truetype(font_path,45) if Path(font_path).exists() else ImageFont.load_default()
        import textwrap
        for line_no, line in enumerate(textwrap.wrap(scene.action.capitalize(),27)[:4]):
            draw.text((95,1490+line_no*65),line,font=font,fill='white')
        draw.text((70,100),f'{index+1}/4',font=font,fill=color)
        image.save(destination)


def select_providers(db, now=None):
    provider = os.getenv('BAMLOOP_STORY_PROVIDER','local').lower()
    image = os.getenv('BAMLOOP_IMAGE_PROVIDER','local').lower()
    video = os.getenv('BAMLOOP_VIDEO_PROVIDER','local').lower()
    budget = max(0,float(os.getenv('BAMLOOP_DAILY_AI_BUDGET_USD','0')))
    estimated = max(0,float(os.getenv('BAMLOOP_AI_ESTIMATED_COST_USD','1')))
    spent = 0.0
    if db is not None:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        zone=ZoneInfo(os.getenv('CHANNEL_TIMEZONE','Europe/Istanbul'))
        start=datetime.now(zone).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
        spent=float(db.execute('SELECT COALESCE(SUM(COALESCE(actual_cost,estimated_cost)),0) FROM publish_queue WHERE channel=? AND created_at>=?',('bamloop',start)).fetchone()[0])
    if (provider,image,video) != ('local','local','local') and spent + estimated <= budget:
        # Unsupported providers cannot spend money; fail closed until installed.
        raise RuntimeError('Configured paid AI provider has no installed adapter')
    return LocalStoryProvider(), LocalImageProvider(), 'zero-cost-local', 0.0, budget


def create_story_video(seed: str, output_dir: str, *, voice_fixture: Path | None = None):
    story_provider, image_provider, provider, cost, _ = select_providers(None)
    if float(os.getenv('BAMLOOP_DAILY_AI_BUDGET_USD','0')) != 0:
        raise RuntimeError('Zero-cost mode requires BAMLOOP_DAILY_AI_BUDGET_USD=0')
    story = story_provider.create(seed)
    output = Path(output_dir); output.mkdir(parents=True,exist_ok=True)
    content_hash=hashlib.sha256(story.idea.encode()).hexdigest()[:16]
    final=output/f'story-{content_hash}.mp4'
    if final.exists():
        _validate_short(final)
        return final, {'title':story.idea[:90]+' #Shorts','description':'Özgün kısa kurgu. #Shorts #hikaye','tags':['hikaye','shorts','kurgu']}, story, provider, cost
    with tempfile.TemporaryDirectory(dir=output) as tmp:
        folder=Path(tmp); clips=[]
        scene_seconds=max(6,int(os.getenv('BAMLOOP_STORY_SCENE_SECONDS','9')))
        for i, scene in enumerate(story.scenes):
            frame=folder/f'{i}.png'; clip=folder/f'{i}.mp4'
            image_provider.render(scene,frame,i)
            prop=folder/f'{i}-prop.png'
            overlay=Image.new('RGBA',(180,180),(0,0,0,0)); marker=ImageDraw.Draw(overlay)
            marker.ellipse((12,12,166,166),fill=('#f8e362','#9fe8ec','#f693ac','#a9f2ae')[i],outline='white',width=8)
            marker.ellipse((62,55,81,74),fill='#101b2b');marker.ellipse((105,55,124,74),fill='#101b2b')
            overlay.save(prop)
            subprocess.run(['ffmpeg','-y','-loglevel','error','-loop','1','-framerate','24','-i',str(frame),
                '-loop','1','-framerate','24','-i',str(prop),'-t',str(scene_seconds),
                '-filter_complex',"[0:v]scale=1240:2205,crop=1080:1920:x='80+55*sin(t*0.55)':y='140+55*cos(t*0.47)',eq=contrast=1.05:saturation=1.08[bg];[1:v]scale=210:210,format=rgba[prop];[bg][prop]overlay=x='250+230*sin(t*0.9)':y='1160+150*cos(t*0.72)':eval=frame,fade=t=in:st=0:d=.18,fade=t=out:st='max(0,'+str(scene_seconds)+'-.22)':d=.22,fps=30,format=yuv420p[v]",
                '-map','[v]','-c:v','libx264','-preset','ultrafast','-crf','27','-threads','2',str(clip)],check=True,timeout=180)
            clips.append(clip)
        concat=folder/'list.txt'; concat.write_text(''.join(f"file '{clip}'
" for clip in clips))
        visuals=folder/'visuals.mp4'
        subprocess.run(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',str(concat),'-c','copy',str(visuals)],check=True,timeout=60)
        narration=folder/'voice.wav'
        if voice_fixture:
            import shutil
            shutil.copyfile(voice_fixture,narration)
        else:
            speech=' '.join(scene.narration for scene in story.scenes)
            import shutil
            binary=shutil.which('espeak-ng')
            if not binary: raise RuntimeError('espeak-ng required for local narration')
            subprocess.run([binary,'-v','tr','-s','160','-w',str(narration),speech],check=True,timeout=90)
        music=os.getenv('BAMLOOP_MUSIC_FILE','')
        bed=['-stream_loop','-1','-i',music] if music and Path(music).is_file() else ['-stream_loop','-1','-i',str(instrumental(output/'original-bed.wav'))]
        subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(visuals),'-i',str(narration),*bed,
            '-filter_complex','[1:a]apad,volume=1.3,asplit=2[side][main];[2:a]volume=0.18[b];[b][side]sidechaincompress=threshold=0.03:ratio=8:detection=rms[d];[main][d]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]',
            '-map','0:v','-map','[a]','-t',str(scene_seconds*len(story.scenes)),'-c:v','copy','-c:a','aac','-b:a','128k','-movflags','+faststart',str(final)],check=True,timeout=180)
    _validate_short(final)
    return final, {'title':story.idea[:90]+' #Shorts','description':'Özgün kısa kurgu. #Shorts #hikaye','tags':['hikaye','shorts','kurgu']}, story, provider, cost
