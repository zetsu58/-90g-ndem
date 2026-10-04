import React from 'react';
import {AbsoluteFill,Audio,Img,OffthreadVideo,Sequence,interpolate,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';

type Scene={start:number;duration:number;caption?:string;mediaIndex?:number;motion?:string;section?:string};
type Beat={start:number;duration:number;mediaIndex:number;sceneIndex?:number;motion?:string};
type CaptionToken={text:string;startMs:number;endMs:number};
type CaptionPage={text:string;startMs:number;endMs:number;tokens?:CaptionToken[]};
export type ShortProps={title:string;caption:string;duration:number;kind:'football'|'meme'|'explainer';media:string[];audio?:string;music?:string;contentFormat?:'short'|'video';scenes?:Scene[];beats?:Beat[];captions?:CaptionPage[]};

const isVideo=(src:string)=>/\.(mp4|mov|webm|m4v)$/i.test(src);
const clampText=(value:string,limit:number)=>value.length<=limit?value:`${value.slice(0,Math.max(0,limit-1)).trim()}…`;

export const ShortVideo:React.FC<ShortProps>=(p)=>{
  const f=useCurrentFrame();
  const {fps}=useVideoConfig();
  const media=p.media||[];
  const long=p.contentFormat==='video';
  const seconds=f/fps;
  const currentMs=seconds*1000;
  const scenes=p.scenes||[];
  const beats=p.beats||[];
  const captions=p.captions||[];
  const scene=long&&scenes.length?scenes.find((x)=>seconds>=x.start&&seconds<x.start+x.duration)??scenes[scenes.length-1]:undefined;
  const beat=long&&beats.length?beats.find((x)=>seconds>=x.start&&seconds<x.start+x.duration)??beats[beats.length-1]:undefined;
  const captionPage=long&&captions.length?captions.find((x)=>currentMs>=x.startMs&&currentMs<x.endMs):undefined;
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
    {long?<AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.26) 0%,rgba(0,0,0,.01) 42%,rgba(0,0,0,.48) 100%)'}}/>:<AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.12),rgba(0,0,0,.72))'}}/>}
    {long?
      <>
        <div style={{position:'absolute',top:28,left:38,fontSize:18,fontWeight:900,letterSpacing:1.1,textShadow:'0 2px 10px rgba(0,0,0,.8)'}}>{p.kind==='football'?'90+ GÜNDEM':'BAMLOOP'}</div>
        {section&&<div style={{position:'absolute',top:29,right:38,fontSize:15,fontWeight:700,letterSpacing:1.2,opacity:.88,textShadow:'0 2px 8px #000'}}>{section}</div>}
        <div style={{position:'absolute',left:38,bottom:105,maxWidth:'68%',opacity:lowerThirdOpacity,background:'rgba(5,8,13,.68)',borderLeft:'4px solid rgba(255,255,255,.92)',padding:'10px 15px 11px 15px',fontSize:23,fontWeight:740,lineHeight:1.16,textShadow:'0 2px 8px rgba(0,0,0,.8)'}}>
          {lowerThird}
        </div>
        {captionPage&&<div style={{position:'absolute',left:'12%',right:'12%',bottom:28,textAlign:'center',fontSize:27,fontWeight:780,lineHeight:1.18,textShadow:'0 2px 8px #000',background:'rgba(0,0,0,.50)',borderRadius:8,padding:'8px 13px'}}>
          {(captionPage.tokens&&captionPage.tokens.length?captionPage.tokens:[{text:captionPage.text,startMs:captionPage.startMs,endMs:captionPage.endMs}]).map((token,index)=>{
            const active=currentMs>=token.startMs&&currentMs<token.endMs;
            return <span key={`${token.startMs}-${index}`} style={{color:active?'#ffd54a':'white'}}>{token.text}{index<((captionPage.tokens?.length||1)-1)?' ':''}</span>;
          })}
        </div>}
      </>:
      <>
        <div style={{position:'absolute',top:70,left:55,right:55,fontSize:32,fontWeight:900}}>{p.kind==='football'?'90+ GÜNDEM':'BAMLOOP'}</div>
        <div style={{position:'absolute',left:55,right:55,bottom:260,fontSize:68,fontWeight:900,lineHeight:1.04,textShadow:'0 4px 18px #000',whiteSpace:'pre-line'}}>{p.caption||p.title}</div>
        <Sequence from={0}><div style={{position:'absolute',bottom:120,left:55,fontSize:28,fontWeight:800}}>{p.kind==='football'?'FUTBOL • SON DAKİKA':'SHORTS • VIRAL'}</div></Sequence>
      </>
    }
    {p.audio&&<Audio src={staticFile(p.audio)}/>}
    {p.music&&<Audio src={staticFile(p.music)} volume={long?0.10:0.18} loop={long}/>}
  </AbsoluteFill>;
};
