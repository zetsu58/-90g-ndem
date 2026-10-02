import React from 'react';
import {AbsoluteFill,Audio,Img,OffthreadVideo,Sequence,interpolate,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';

type Scene={start:number;duration:number;caption?:string;mediaIndex?:number;motion?:string};
export type ShortProps={title:string;caption:string;duration:number;kind:'football'|'meme'|'explainer';media:string[];audio?:string;music?:string;contentFormat?:'short'|'video';scenes?:Scene[]};

const isVideo=(src:string)=>/\.(mp4|mov|webm|m4v)$/i.test(src);

export const ShortVideo:React.FC<ShortProps>=(p)=>{
  const f=useCurrentFrame();
  const {fps}=useVideoConfig();
  const media=p.media||[];
  const long=p.contentFormat==='video';
  const seconds=f/fps;
  const scenes=p.scenes||[];
  const scene=long&&scenes.length?scenes.find((x)=>seconds>=x.start&&seconds<x.start+x.duration)??scenes[scenes.length-1]:undefined;
  const fallbackBeat=Math.max(1,Math.floor(fps*2.6));
  const sceneStart=scene?Math.floor(scene.start*fps):0;
  const sceneFrames=scene?Math.max(1,Math.floor(scene.duration*fps)):fallbackBeat;
  const local=scene?Math.max(0,f-sceneStart):(f%fallbackBeat);
  const i=media.length?(scene?Math.abs(scene.mediaIndex??scenes.indexOf(scene))%media.length:Math.floor(f/fallbackBeat)%media.length):0;
  const scale=interpolate(local,[0,sceneFrames],[1.03,1.11],{extrapolateRight:'clamp'});
  const src=media[i]?staticFile(media[i]):null;
  const caption=scene?.caption||p.caption||p.title;
  return <AbsoluteFill style={{backgroundColor:'#07111f',fontFamily:'Arial,sans-serif',color:'white'}}>
    {src&&(isVideo(media[i])?<OffthreadVideo src={src} muted style={{width:'100%',height:'100%',objectFit:'cover',transform:`scale(${scale})`}}/>:<Img src={src} style={{width:'100%',height:'100%',objectFit:'cover',transform:`scale(${scale})`}}/>)}
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.12),rgba(0,0,0,.72))'}}/>
    <div style={{position:'absolute',top:long?35:70,left:55,right:55,fontSize:long?24:32,fontWeight:900}}>{p.kind==='football'?'90+ GÜNDEM':'BAMLOOP'}</div>
    <div style={{position:'absolute',left:55,right:55,bottom:long?110:260,fontSize:long?42:68,fontWeight:900,lineHeight:1.04,textShadow:'0 4px 18px #000',whiteSpace:'pre-line'}}>{caption}</div>
    {p.audio&&<Audio src={staticFile(p.audio)}/>}
    {p.music&&<Audio src={staticFile(p.music)} volume={0.18} loop={long}/>}
    <Sequence from={0}><div style={{position:'absolute',bottom:long?38:120,left:55,fontSize:long?20:28,fontWeight:800}}>{long?(p.kind==='football'?'FUTBOL • DOSYA':'BİLGİ • DOSYA'):(p.kind==='football'?'FUTBOL • SON DAKİKA':'SHORTS • VIRAL')}</div></Sequence>
  </AbsoluteFill>;
};
