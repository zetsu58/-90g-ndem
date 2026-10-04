import React from 'react';
import {AbsoluteFill,Audio,Img,OffthreadVideo,Sequence,interpolate,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';

type Scene={start:number;duration:number;caption?:string;mediaIndex?:number;motion?:string;section?:string};
type Beat={start:number;duration:number;mediaIndex:number;sceneIndex?:number;motion?:string};
export type ShortProps={title:string;caption:string;duration:number;kind:'football'|'meme'|'explainer';media:string[];audio?:string;music?:string;contentFormat?:'short'|'video';scenes?:Scene[];beats?:Beat[]};

const isVideo=(src:string)=>/\.(mp4|mov|webm|m4v)$/i.test(src);
const clampText=(value:string,limit:number)=>value.length<=limit?value:`${value.slice(0,Math.max(0,limit-1)).trim()}…`;

export const ShortVideo:React.FC<ShortProps>=(p)=>{
  const f=useCurrentFrame();
  const {fps}=useVideoConfig();
  const media=p.media||[];
  const long=p.contentFormat==='video';
  const seconds=f/fps;
  const scenes=p.scenes||[];
  const beats=p.beats||[];
  const scene=long&&scenes.length?scenes.find((x)=>seconds>=x.start&&seconds<x.start+x.duration)??scenes[scenes.length-1]:undefined;
  const beat=long&&beats.length?beats.find((x)=>seconds>=x.start&&seconds<x.start+x.duration)??beats[beats.length-1]:undefined;
  const fallbackBeat=Math.max(1,Math.floor(fps*2.6));
  const activeStart=beat?Math.floor(beat.start*fps):(scene?Math.floor(scene.start*fps):0);
  const activeFrames=beat?Math.max(1,Math.floor(beat.duration*fps)):(scene?Math.max(1,Math.floor(scene.duration*fps)):fallbackBeat);
  const local=Math.max(0,f-activeStart);
  const i=media.length?(long?(Math.abs(beat?.mediaIndex??scene?.mediaIndex??0)%media.length):Math.floor(f/fallbackBeat)%media.length):0;
  const scale=interpolate(local,[0,activeFrames],[1.02,1.08],{extrapolateRight:'clamp'});
  const src=media[i]?staticFile(media[i]):null;
  const sceneElapsed=scene?Math.max(0,seconds-scene.start):0;
  const lowerThirdOpacity=long&&scene?interpolate(sceneElapsed,[0,0.35,3.8,4.5],[0,1,1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}):1;
  const section=(scene?.section||'').replace(/_/g,' ').toUpperCase();
  const lowerThird=clampText(scene?.caption||p.caption||p.title,105);
  return <AbsoluteFill style={{backgroundColor:'#05080d',fontFamily:'Arial,sans-serif',color:'white',overflow:'hidden'}}>
    {src&&(isVideo(media[i])?<OffthreadVideo src={src} muted style={{width:'100%',height:'100%',objectFit:'cover',transform:`scale(${scale})`}}/>:<Img src={src} style={{width:'100%',height:'100%',objectFit:'cover',transform:`scale(${scale})`}}/>)}
    {long?<AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.28) 0%,rgba(0,0,0,.02) 42%,rgba(0,0,0,.42) 100%)'}}/>:<AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.12),rgba(0,0,0,.72))'}}/>}
    {long?
      <>
        <div style={{position:'absolute',top:28,left:38,fontSize:18,fontWeight:900,letterSpacing:1.1,textShadow:'0 2px 10px rgba(0,0,0,.8)'}}>{p.kind==='football'?'90+ GÜNDEM':'BAMLOOP'}</div>
        {section&&<div style={{position:'absolute',top:29,right:38,fontSize:15,fontWeight:700,letterSpacing:1.2,opacity:.88,textShadow:'0 2px 8px #000'}}>{section}</div>}
        <div style={{position:'absolute',left:38,bottom:42,maxWidth:'78%',opacity:lowerThirdOpacity,background:'rgba(5,8,13,.72)',borderLeft:'4px solid rgba(255,255,255,.92)',padding:'14px 18px 15px 18px',fontSize:26,fontWeight:750,lineHeight:1.18,textShadow:'0 2px 8px rgba(0,0,0,.8)'}}>
          {lowerThird}
        </div>
      </>:
      <>
        <div style={{position:'absolute',top:70,left:55,right:55,fontSize:32,fontWeight:900}}>{p.kind==='football'?'90+ GÜNDEM':'BAMLOOP'}</div>
        <div style={{position:'absolute',left:55,right:55,bottom:260,fontSize:68,fontWeight:900,lineHeight:1.04,textShadow:'0 4px 18px #000',whiteSpace:'pre-line'}}>{p.caption||p.title}</div>
        <Sequence from={0}><div style={{position:'absolute',bottom:120,left:55,fontSize:28,fontWeight:800}}>{p.kind==='football'?'FUTBOL • SON DAKİKA':'SHORTS • VIRAL'}</div></Sequence>
      </>
    }
    {p.audio&&<Audio src={staticFile(p.audio)}/>}
    {p.music&&<Audio src={staticFile(p.music)} volume={long?0.12:0.18} loop={long}/>}
  </AbsoluteFill>;
};
