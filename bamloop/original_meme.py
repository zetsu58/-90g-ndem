"""Original animated comedy, with a finite, deduplicated story bank.

Different comic actions are drawn frame by frame; this is not a stock-clip
caption generator. No real player likenesses, external clips, or paid AI calls.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CONTRACT = "original-animated-meme-v1"
WIDTH, HEIGHT, FPS = 720, 1280, 24
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Script, action and payoff are authored together. Changing a caption alone
# never creates another eligible episode. Expand this bank with new stories.
STORIES = (
    ("football", "penalty_cloud", "Penaltıyı kaleci değil, bulut kurtardı", "ŞUT: HAZIR", "TOP: BULUTA TAŞINDI", "sky"),
    ("football", "penalty_return", "Top geri geldi, özgüven gelmedi", "BU ŞUT KESİN GOL", "TOP: İADE TALEBİ", "return"),
    ("football", "keeper_wrong", "Kaleci doğru tahmin etti... diğer kalede", "KÖŞEYİ BİLİYORUM", "DİĞER KÖŞEYİ DEMİŞTİM", "wrong"),
    ("football", "keeper_phone", "Kalecinin ekran süresi maça taştı", "BİR BİLDİRİME BAKACAĞIM", "GOL BİLDİRİMİ GELDİ", "phone"),
    ("football", "goal_shrinks", "Şut gelince kale küçüldü", "ANTRENMANDA HEP GOL", "MAÇTA KALE: CEP BOYU", "shrink"),
    ("football", "goal_runs", "Bu sefer kale kaçtı", "BU MESAFEDEN KAÇMAZ", "KALE: BEN KAÇARIM", "escape"),
    ("football", "ball_queue", "Toplar bile transfer sırası bekliyor", "YENİ TRANSFER GELİYOR", "SIRA NUMARASI: 999", "queue"),
    ("football", "extra_time", "Son düdük beklerken uzatma uzadı", "SON ATAK, SONRA BİTİYOR", "SON ATAĞIN SON ATAĞI", "clock"),
    ("global", "alarm_runs", "Alarmı susturacaktım, alarm kaçtı", "BEŞ DAKİKA DAHA", "ALARM: ÖNCE BENİ YAKALA", "alarm"),
    ("global", "cat_keyboard", "İşi bitirecektim, kedi gönderdi", "SON BİR DÜZELTME", "KEDİ: GÖNDERİLDİ", "keyboard"),
    ("global", "cat_charger", "Telefon değil kedi şarj oldu", "ŞARJ ALETİNİ BULDUM", "KEDİ: ARTIK BENİM", "charger"),
    ("global", "wifi_escape", "Tam gönderirken Wi-Fi kaçtı", "İNTERNET ÇOK HIZLI", "BAĞLANTI: GÖRÜŞÜRÜZ", "wifi"),
    ("global", "loading_reverse", "Yüzde 99'dan geriye sayan güncelleme", "BİR SANİYE KALDI", "GÜNCELLEME: BAŞA DÖNELİM", "loading"),
    ("global", "battery_empty", "Şarj yüzde bir, umut yüzde yüz", "ŞARJA KADAR YETER", "TELEFON: BEN ÇIKIYORUM", "battery"),
    ("global", "coffee_falls", "Kahve beni uyandırdı, farklı şekilde", "KAHVEYLE TOPARLANIRIM", "MASA DA UYANDI", "coffee"),
    ("global", "meeting_cat", "Kameram kapalı sanıyordum", "TOPLANTIDA SAKİN DUR", "KEDİ: SAHNE BENİM", "meeting"),
    ("global", "shopping_cart", "Tek bir şey alacaktım", "SADECE EKMEK ALACAĞIM", "SEPET: TAM KADRO", "cart"),
    ("global", "delivery_runs", "Kargoyu bekledim, kargo beni beklemedi", "KAPIYA GELDİM", "KARGO: TUR ATIP GELİRİM", "delivery"),
    ("global", "robot_clean", "Robot evi değil beni topladı", "EV TEMİZLENECEK", "ROBOT: ÖNCE SEN", "robot"),
    ("global", "social_battery", "Selam verecektim, sosyal pil bitti", "İKİ DAKİKA SOHBET", "SOSYAL PİL: YOK", "social"),
    ("global", "umbrella_flip", "Şemsiye havayı farklı yorumladı", "YAĞMURA HAZIRIM", "ŞEMSİYE: RÜZGÂRA HAZIRIM", "umbrella"),
    ("global", "gym_weight", "Ağırlık değil özgüven düştü", "BUGÜN REKOR KIRIYORUM", "REKOR: EVE DÖNÜŞ HIZI", "gym"),
    ("global", "game_lag", "Oyunda karakter yürüdü, bağlantı oturdu", "SON HAMLE BENDE", "İNTERNET: BENDE DEĞİL", "game"),
    ("global", "budget_gone", "Maaş geldi, faturalar karşıladı", "BUGÜN ZENGİNİM", "FATURALAR: HOŞ GELDİN", "budget"),
)


def story_bank(category):
    return [dict(category=c, id=i, title=t, setup=s, payoff=p, action=a, duration=12.0,
                 punchline_at=4.0, renderer_version=1) for c, i, t, s, p, a in STORIES if c == category]


def identity(story):
    # Same actual story keeps its identity through editorial text corrections.
    return hashlib.sha256((CONTRACT + "|" + story['id']).encode()).hexdigest()[:24]


def validate_metadata(metadata):
    story = next((s for s in story_bank(metadata.get('meme_category'))
                  if s['id'] == metadata.get('story_id')), None)
    if (not story or metadata.get('meme_contract') != CONTRACT or
            metadata.get('original_story') != story or
            metadata.get('content_id') != identity(story) or
            metadata.get('content_format') != 'short'):
        raise ValueError('original_meme_contract_invalid')
    return story


def _font(size):
    return ImageFont.truetype(FONT_PATH, size)


def _text(draw, text, y, size=38, color='white'):
    font = _font(size)
    words, lines, line = text.split(), [], ''
    for word in words:
        candidate = (line + ' ' + word).strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] > 620 and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    for line in lines:
        width = draw.textbbox((0, 0), line, font=font)[2]
        draw.text(((WIDTH - width) / 2, y), line, font=font, fill=color)
        y += size + 12


def _person(draw, x, y, *, color='#ffd166', reaction=False, lift=0):
    draw.ellipse((x-36, y-110, x+36, y-38), fill='#f3c6a5', outline='#13223c', width=4)
    draw.rounded_rectangle((x-40, y-38, x+40, y+65), radius=15, fill=color)
    draw.line((x-20,y+65,x-35,y+128),fill='#d7e4fa',width=17)
    draw.line((x+20,y+65,x+35,y+128),fill='#d7e4fa',width=17)
    draw.line((x-40,y-15,x-76,y+30-lift),fill='#f3c6a5',width=13)
    draw.line((x+40,y-15,x+76,y+30-lift),fill='#f3c6a5',width=13)
    for offset in (-12,12):
        draw.ellipse((x+offset-4,y-86,x+offset+4,y-76),fill='#13223c')
    if reaction:
        draw.ellipse((x-10,y-65,x+10,y-44),fill='#13223c')
    else:
        draw.arc((x-16,y-76,x+16,y-48),0,180,fill='#13223c',width=3)


def _ball(draw, x, y, radius=25):
    draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill='white',outline='#111827',width=3)
    draw.regular_polygon((x,y,radius*.45),n_sides=5,fill='#111827')


def _cat(draw, x, y, phase):
    draw.ellipse((x-48,y-42,x+48,y+36),fill='#ffae57')
    draw.polygon(((x-35,y-15),(x-40,y-70),(x-5,y-42)),fill='#ffae57')
    draw.polygon(((x+35,y-15),(x+40,y-70),(x+5,y-42)),fill='#ffae57')
    for offset in (-17,17):
        draw.ellipse((x+offset-4,y-10,x+offset+4,y-2),fill='#17233b')
    draw.line((x+38,y+17,x+85,y+8+15*math.sin(phase)),fill='#ffae57',width=13)


def frame(story, t):
    image = Image.new('RGB',(WIDTH,HEIGHT),'#101a30')
    draw = ImageDraw.Draw(image)
    football = story['category']=='football'
    draw.rounded_rectangle((28,270,692,1050),radius=36,fill='#174a39' if football else '#20314e')
    _text(draw, 'FUTBOL MEME' if football else 'GLOBAL MEME', 65, 25, '#8edcf0')
    _text(draw, story['setup'] if t < story['punchline_at'] else story['payoff'], 140)
    # An actor or prop is already moving in frame zero; no logo introduction.
    p = min(1.0,max(0.0,(t-3.4)/2.8))
    bounce = 8*math.sin(t*5)
    action = story['action']
    if football:
        draw.line((55,965,665,965),fill='#d3f5de',width=4)
        draw.arc((65,710,470,1100),180,360,fill='#d3f5de',width=3)
        gx, gy, gw, gh = 485, 535, 150, 205
        if action=='escape': gx += 180*p
        if action=='shrink': gw,gh = 150*(1-.72*p),205*(1-.72*p)
        draw.rectangle((gx,gy,gx+gw,gy+gh),outline='white',width=6)
        for i in range(1,5):
            draw.line((gx+gw*i/5,gy,gx+gw*i/5,gy+gh),fill='#b6cfc9',width=2)
        _person(draw,160,795,color='#ffcf56',reaction=p>.8,lift=25*math.sin(t*6))
        keeper_x = 560 - (170*p if action=='wrong' else 0)
        _person(draw,keeper_x,655,color='#b795ff',reaction=p>.8)
        if action=='sky': bx,by=220+300*p,895-650*p
        elif action=='return': bx,by=220+340*math.sin(p*math.pi),895-230*math.sin(p*math.pi)
        else: bx,by=220+380*p,895-215*p
        _ball(draw,bx,by+bounce)
        if action=='phone':
            draw.rounded_rectangle((keeper_x+35,610,keeper_x+75,680),radius=7,fill='#7de1ee')
        elif action=='queue':
            for i in range(5): _ball(draw,105+95*i,980-12*math.sin(t+i),18)
        elif action=='clock':
            draw.ellipse((270,390,420,540),fill='#eef7ff')
            angle=t*(2 if t<4 else 10)
            draw.line((345,465,345+55*math.sin(angle),465-55*math.cos(angle)),fill='#17243a',width=7)
    else:
        draw.rounded_rectangle((75,820,650,855),radius=8,fill='#a8b5cb')
        _person(draw,170,685,reaction=p>.8,lift=30*math.sin(t*4))
        if action in {'keyboard','charger','meeting'}:
            draw.rounded_rectangle((340,530,570,700),radius=14,fill='#071224',outline='#7de1ee',width=5)
            _text(draw,'GÖNDER' if action=='keyboard' else 'BAĞLANDI',580,20,'#7de1ee')
            _cat(draw,600-180*p,785-180*math.sin(p*math.pi),t*5)
        elif action in {'alarm','social'}:
            x=465+170*p
            draw.ellipse((x-70,600,x+70,740),fill='#ff7676')
            draw.line((x,670,x+35*math.sin(t*8),670-35*math.cos(t*8)),fill='white',width=6)
            draw.line((x-35,740,x-55,780+bounce),fill='#ff7676',width=13)
            draw.line((x+35,740,x+55,780-bounce),fill='#ff7676',width=13)
        elif action in {'wifi','loading','battery','game','budget'}:
            draw.rounded_rectangle((320,450,630,745),radius=24,fill='#071224',outline='#7de1ee',width=5)
            if action=='wifi':
                for i in range(3): draw.arc((375-i*23+180*p,550-i*23,540+i*23+180*p,695+i*23),205,335,fill='#7de1ee',width=10)
            elif action=='game': _person(draw,400+100*math.sin(t*4)*(1-p),600,color='#7de1ee')
            else:
                labels={'loading':'YÜKLENİYOR','battery':'ŞARJ','budget':'BAKİYE'}
                _text(draw,labels[action],480,26,'#7de1ee')
                value=max(0,99-int(99*p))
                _text(draw,f'%{value}',555,60,'#ff7676' if p>.7 else 'white')
                draw.rectangle((350,675,350+230*(1-p),700),fill='#7de1ee')
        elif action=='coffee':
            x,y=450+110*p,750+170*p*p
            draw.rounded_rectangle((x-35,y-60,x+35,y),radius=10,fill='#ffcf56')
            if p>.5: draw.ellipse((370,803,630,826),fill='#815331')
        elif action in {'cart','delivery','robot'}:
            x=440+140*math.sin(p*math.pi)
            draw.rounded_rectangle((x-75,690,x+75,790),radius=15,fill='#7de1ee')
            for offset in (-50,50): draw.ellipse((x+offset-15,780,x+offset+15,810),fill='#071224')
            if action=='cart':
                for i in range(int(1+8*p)): draw.rectangle((x-65+i%4*34,680-i//4*38,x-39+i%4*34,710-i//4*38),fill='#ffcf56')
            elif action=='robot': _cat(draw,x,660,t)
            else: draw.line((x-70,650,x+70,650),fill='#ffcf56',width=15)
        elif action=='umbrella':
            x,y=455,590
            draw.pieslice((x-115,y-110,x+115,y+110),180 if p<.5 else 0,360 if p<.5 else 180,fill='#b795ff')
            draw.line((x,y,x,y+200),fill='white',width=7)
            for i in range(14):
                rx=75+(i*47)%590; ry=330+(t*200+i*50)%650
                draw.line((rx,ry,rx-15,ry+35),fill='#7de1ee',width=3)
        elif action=='gym':
            y=650+130*p
            draw.line((350,y,610,y),fill='white',width=12)
            for x in (355,605): draw.rounded_rectangle((x-20,y-55,x+20,y+55),radius=8,fill='#b795ff')
    if t > 7:
        _text(draw,'BENİM PLAN / HAYATIN PLANI',1095,24,'#8edcf0')
    _text(draw,'BAMLOOP • ÖZGÜN ANİMASYON',1190,18,'#8396b8')
    return image


def build_original_video(story, output_dir='storage/bamloop'):
    from .reaction_meme import _sound
    from viral_futbol.youtube_publisher import _validate_short
    directory=Path(output_dir); directory.mkdir(parents=True,exist_ok=True)
    content_id=identity(story)
    output=directory/f'original-{content_id}.mp4'
    pending=directory/f'original-{content_id}.pending.mp4'
    sound=directory/f'original-{content_id}.wav'
    log=directory/f'original-{content_id}.ffmpeg.log'
    metadata={'title':story['title'][:100], 'description':
              '#futbol #mizah #shorts' if story['category']=='football' else '#meme #komik #shorts',
              'tags':['futbol','mizah','shorts'] if story['category']=='football' else ['meme','komedi','shorts'],
              'meme_contract':CONTRACT,'meme_category':story['category'],
              'story_id':story['id'],'original_story':story,'content_id':content_id,
              'content_format':'short','duration_seconds':story['duration'],
              'edit_beats':['visual_setup','animated_action','comic_payoff','reaction'],
              'source_type':'original_animation','language':'tr','hook_variant':'direct_visual'}
    validate_metadata(metadata)
    if output.exists():
        _validate_short(output)
        return output,metadata
    process=None
    try:
        _sound(sound,story['duration'],story['punchline_at'],7)
        with log.open('wb') as stderr:
            process=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-threads','1',
                '-f','rawvideo','-pix_fmt','rgb24','-s',f'{WIDTH}x{HEIGHT}','-r',str(FPS),'-i','pipe:0',
                '-i',str(sound),'-c:v','libx264','-threads','1','-preset','ultrafast','-crf','23',
                '-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-t',str(story['duration']),
                '-movflags','+faststart',str(pending)],stdin=subprocess.PIPE,stderr=stderr)
            for index in range(int(FPS*story['duration'])):
                process.stdin.write(frame(story,index/FPS).tobytes())
            process.stdin.close()
            if process.wait(timeout=90): raise RuntimeError('original_meme_render_failed')
        _validate_short(pending)
        pending.replace(output)
        return output,metadata
    finally:
        if process and process.poll() is None:
            process.kill(); process.wait(timeout=10)
        for path in (sound,pending,log): path.unlink(missing_ok=True)
