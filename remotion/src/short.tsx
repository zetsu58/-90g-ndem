import React from 'react';
import {AbsoluteFill,Audio,Img,OffthreadVideo,Sequence,interpolate,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';
export type ShortProps={title:string;caption:string;duration:number;kind:'football'|'meme';media:string[];audio?:string;music?:string};
const isVideo=(src:string)=>/\.(mp4|mov|webm|m4v)$/i.test(src);
export const ShortVideo:React.FC<ShortProps>=(p)=>{
  const f=useCurrentFrame();const {fps}=useVideoConfig();const media=p.media||[];
  const beat=Math.max(1,Math.floor(fps*2.6));const i=media.length?Math.min(media.length-1,Math.floor(f/beat)%media.length):0;
  const local=f%beat;const scale=interpolate(local,[0,beat],[1.03,1.13],{extrapolateRight:'clamp'});
  const src=media[i]?staticFile(media[i]):null;
  return <AbsoluteFill style={{backgroundColor:'#07111f',fontFamily:'Arial,sans-serif',color:'white'}}>
    {src&&(isVideo(media[i])?<OffthreadVideo src={src} muted style={{width:'100%',height:'100%',objectFit:'cover',transform:`scale(${scale})`}}/>:<Img src={src} style={{width:'100%',height:'100%',objectFit:'cover',transform:`scale(${scale})`}}/>)}
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.12),rgba(0,0,0,.72))'}}/>
    <div style={{position:'absolute',top:70,left:55,right:55,fontSize:32,fontWeight:900}}>{p.kind==='football'?'90+ GÜNDEM':'BAMLOOP'}</div>
    <div style={{position:'absolute',left:55,right:55,bottom:260,fontSize:68,fontWeight:900,lineHeight:1.04,textShadow:'0 4px 18px #000',whiteSpace:'pre-line'}}>{p.caption||p.title}</div>
    {p.audio&&<Audio src={staticFile(p.audio)}/>}
    {p.music&&<Audio src={staticFile(p.music)} volume={0.20}/>}
    <Sequence from={0}><div style={{position:'absolute',bottom:120,left:55,fontSize:28,fontWeight:800}}>{p.kind==='football'?'FUTBOL • SON DAKİKA':'SHORTS • VIRAL'}</div></Sequence>
  </AbsoluteFill>;
};
