import {bundle} from '@remotion/bundler';
import {getCompositions, renderMedia} from '@remotion/renderer';
import path from 'node:path';
import fs from 'node:fs';

const [,,manifestPath,output] = process.argv;
if (!manifestPath || !output) throw new Error('usage: node render.mjs manifest.json output.mp4');

const props = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || '/usr/bin/chromium';
const browserOptions = fs.existsSync(browserExecutable) ? {browserExecutable} : {};

console.log('[remotion] bundle:start', {browserExecutable, exists: fs.existsSync(browserExecutable)});
const serveUrl = await bundle({
  entryPoint: path.resolve('remotion/src/index.ts'),
  publicDir: path.resolve('remotion/public'),
});
console.log('[remotion] bundle:done');

console.log('[remotion] compositions:start');
const comps = await getCompositions(serveUrl, {inputProps: props, ...browserOptions});
console.log('[remotion] compositions:done', comps.map((c) => c.id));

const comp = comps.find((c) => c.id === 'ShortVideo');
if (!comp) throw new Error('ShortVideo composition missing');

console.log('[remotion] render:start');
await renderMedia({
  composition: comp,
  serveUrl,
  codec: 'h264',
  outputLocation: output,
  inputProps: props,
  crf: 20,
  ...browserOptions,
});
console.log('[remotion] render:done');
