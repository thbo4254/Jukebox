// Offline deterministic audio doubles: state-machine evidence, not generated audio evidence.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const path=new URL('../jukebox/static/player.js',import.meta.url);
if(fs.existsSync(path)) vm.runInThisContext(fs.readFileSync(path,'utf8'));
const song=id=>({id,title:id,audio:`/${id}.mp3`});
class AudioDouble {
  paused=true; src=''; currentTime=0;
  async play(){this.paused=false;}
  pause(){this.paused=true;}
}
function setup(dj=async()=>({url:'/intro.mp3',intro:'Welcome'})){
  assert.equal(typeof globalThis.JukeboxPlayer,'function','Player state machine missing');
  const audio=new AudioDouble(); const notes=[];
  const p=new JukeboxPlayer({audio,requestDJ:dj,onChange:()=>{},notice:t=>notes.push(t)});
  return {p,audio,notes};
}
const tick=()=>new Promise(r=>setTimeout(r,0));
test('intentional pause invalidates pending play rejection without a browser-block notice',async()=>{
  const {p,audio,notes}=setup();p.dj=false;let rejectPlay;
  audio.play=()=>new Promise((_,reject)=>{rejectPlay=reject;});
  p.enqueue(song('a'));const pending=p.next();await p.toggle();
  rejectPlay(Object.assign(Error('interrupted by pause'),{name:'AbortError'}));await pending;
  assert.equal(p.paused,true);assert.equal(audio.paused,true);assert.deepEqual(notes,[]);
});
test('stale AbortError after successful same-source resume cannot pause or block queue advance',async()=>{
  const {p,audio,notes}=setup();p.dj=false;let rejectFirst,calls=0;
  audio.play=()=>{
    audio.paused=false;
    return ++calls===1?new Promise((_,reject)=>{rejectFirst=reject;}):Promise.resolve();
  };
  p.enqueue(song('a'));p.enqueue(song('b'));const pending=p.next();
  const src=audio.src;
  await p.toggle();assert.equal(audio.paused,true);
  await p.toggle();assert.equal(audio.src,src);assert.equal(audio.paused,false);
  rejectFirst(Object.assign(Error('old play interrupted'),{name:'AbortError'}));await pending;
  assert.equal(p.paused,false);assert.equal(audio.paused,false);assert.deepEqual(notes,[]);
  audio.onended();await tick();assert.equal(p.current.id,'b');
});
test('DJ ends then music; music ends then next queued track',async()=>{
  const {p,audio}=setup(); p.enqueue(song('a')); p.enqueue(song('b')); await p.next();
  assert.equal(p.phase,'speech'); assert.equal(audio.src,'/intro.mp3');
  audio.onended(); await tick(); assert.equal(p.phase,'music'); assert.equal(audio.src,'/api/songs/a/audio');
  audio.onended(); await tick(); assert.equal(p.current.id,'b'); assert.equal(p.phase,'speech');
});
test('skip during pending speech starts associated music and ignores stale response',async()=>{
  let resolve;const {p,audio}=setup(()=>new Promise(r=>resolve=r)); p.enqueue(song('a')); const pending=p.next(); await tick();
  await p.skip(); assert.equal(audio.src,'/api/songs/a/audio'); assert.equal(p.phase,'music');
  resolve({url:'/stale.mp3',intro:'old'}); await pending; assert.equal(audio.src,'/api/songs/a/audio');
});
test('pause while DJ loads remains paused when response arrives',async()=>{
  let resolve;const {p,audio}=setup(()=>new Promise(r=>resolve=r)); p.enqueue(song('a')); const pending=p.next(); await tick();
  await p.toggle(); resolve({url:'/intro.mp3',intro:'x'}); await pending;
  assert.equal(audio.paused,true); assert.equal(p.paused,true);
  await p.toggle(); assert.equal(audio.paused,false);
});
test('skip during speech starts this song; skip music advances queue',async()=>{
  const {p,audio}=setup();p.enqueue(song('a'));p.enqueue(song('b'));await p.next();
  await p.skip();assert.equal(p.current.id,'a');assert.equal(p.phase,'music');
  await p.skip();assert.equal(p.current.id,'b');assert.equal(p.phase,'speech');
});
test('DJ failure continues music with an understandable notice',async()=>{
  const {p,audio,notes}=setup(async()=>{throw Error('Speech service unavailable')});p.enqueue(song('a'));await p.next();
  assert.equal(p.phase,'music');assert.equal(audio.src,'/api/songs/a/audio');assert.match(notes[0],/Speech service/);
});
test('DJ off bypasses speech and queues are independent',async()=>{
  let calls=0;const {p}=setup(async()=>{calls++;return {url:'/x'}});const {p:other}=setup();p.dj=false;p.enqueue(song('a'));await p.next();
  assert.equal(p.phase,'music');assert.equal(calls,0);assert.equal(other.queue.length,0);
});
test('autoplay rejection leaves resumable paused state',async()=>{
  const {p,audio,notes}=setup();p.dj=false;audio.play=async()=>{throw Error('NotAllowedError')};p.enqueue(song('a'));await p.next();
  assert.equal(p.paused,true);assert.match(notes.at(-1),/Play/);
});
test('bundled sample filenames never override the protected audio route',async()=>{
  const {p,audio}=setup();p.dj=false;p.enqueue({id:'sample-amber-after-hours',title:'Amber',audio:'audio.mp3'});await p.next();
  assert.equal(audio.src,'/api/songs/sample-amber-after-hours/audio');
});
test('late speech play rejection cannot pause music after speech decoder failure',async()=>{
  const {p,audio}=setup();let rejectSpeech;
  audio.play=()=>audio.src==='/intro.mp3'?new Promise((_,reject)=>{rejectSpeech=reject;}):(audio.paused=false,Promise.resolve());
  p.enqueue(song('a'));const pending=p.next();await tick();audio.onerror();await tick();
  assert.equal(p.phase,'music');rejectSpeech(Object.assign(Error('unsupported speech'),{name:'NotSupportedError'}));await pending;
  assert.equal(p.paused,false);assert.equal(audio.paused,false);
});
test('unsupported music gives decode guidance rather than an autoplay diagnosis',async()=>{
  const {p,audio,notes}=setup();p.dj=false;audio.play=async()=>{throw Object.assign(Error('bad media'),{name:'NotSupportedError'});};
  p.enqueue(song('a'));await p.next();assert.equal(p.paused,true);assert.match(notes.at(-1),/could not play/);
});
test('queue exhaustion clears current and pauses',async()=>{
  const {p,audio}=setup();p.dj=false;p.enqueue(song('a'));await p.next();audio.onended();await tick();
  assert.equal(p.phase,'idle');assert.equal(p.current,null);assert.equal(audio.paused,true);
});
