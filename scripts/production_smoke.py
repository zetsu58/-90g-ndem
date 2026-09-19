"""Credential-free end-to-end video smoke; outputs live in a temporary directory."""
from __future__ import annotations
import asyncio
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw
from bamloop.engine import MemeIdea, build_video
from bamloop.story import create_story_video
from viral_futbol.lite_video import render_lite_video
from viral_futbol.youtube_publisher import _validate_short


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp)
        source=base/'clip.mp4'
        subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i','testsrc2=size=1080x1920:rate=30','-f','lavfi','-i','sine=frequency=440:duration=7',
             '-t','7','-c:v','libx264','-preset','ultrafast','-threads','2','-c:a','aac',str(source)],check=True,timeout=180)
        meme,_=build_video(MemeIdea('local','BEKLEMEYEN AN','Beklenmedik An'),str(base/'meme'),source.as_uri())
        voice=base/'voice.wav'
        subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i','sine=frequency=330:duration=36','-c:a','pcm_s16le',str(voice)],check=True,timeout=30)
        story,*_=create_story_video('fixture-original',str(base/'story'),voice_fixture=voice)
        async def speech(_text,_voice,path):
            subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i','sine=frequency=350:duration=27','-c:a','libmp3lame',str(path)],check=True,timeout=30)
        def frames(**kwargs):
            result=[]
            for i in range(3):
                image=Image.new('RGB',(1080,1920),('#223344','#335544','#553344')[i]);
                ImageDraw.Draw(image).ellipse((220,350,850,1050),fill='#ddaa77'); path=Path(kwargs['output_dir'])/f'frame{i}.jpg';image.save(path);result.append(path)
            return result
        with patch('viral_futbol.lite_video.download_pexels_frames',side_effect=frames), patch('viral_futbol.lite_video._save_speech',side_effect=speech):
            viral=render_lite_video(story_id='smoke',title='Kulüp yeni sezon kadrosunu duyurdu',sources=['Official'],facts=['Kadronun açıklaması yayımlandı'],language='tr',voice_name='tr-TR-EmelNeural',output_dir=str(base/'viral'))
        results={}
        for name,path in (('viral_futbol',viral),('bamloop_meme',meme),('bamloop_ai_story',story)):
            results[name]=_validate_short(path)
            assert results[name]['width']==1080 and results[name]['height']==1920
            assert results[name]['video_codec']=='h264' and results[name]['audio_codec']=='aac'
            print(json.dumps({'name':name,**results[name]},ensure_ascii=False),flush=True)
        return results

if __name__=='__main__': main()
