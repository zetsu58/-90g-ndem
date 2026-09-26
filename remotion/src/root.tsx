import React from 'react';
import {Composition} from 'remotion';
import {ShortVideo, type ShortProps} from './short';
const defaults: ShortProps={title:'90+ Gündem',caption:'',duration:12,kind:'football',media:[]};
export const Root=()=> <Composition id="ShortVideo" component={ShortVideo} width={1080} height={1920} fps={30} durationInFrames={360} defaultProps={defaults} calculateMetadata={({props})=>({durationInFrames:Math.max(1,Math.ceil(props.duration*30))})}/>;
