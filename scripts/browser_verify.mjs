// Real services, real browser, no fabricated outputs. Generates one short vocal test track.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {connect} from './cdp.mjs';
const c=await connect();const evidence=process.env.REUSE_GENERATED?JSON.parse(fs.readFileSync('docs/evidence/browser.json','utf8')).filter(x=>x.name==='Qwen lyrics reviewed and edited; ACE+FLUX saved'):[];
function record(name,result){evidence.push({name,result});console.log(name,JSON.stringify(result));fs.mkdirSync('docs/evidence',{recursive:true});fs.writeFileSync('docs/evidence/browser.json',JSON.stringify(evidence,null,2));}
try{
 await c.send('Page.reload',{ignoreCache:true});
 await c.sleep(500);
 await c.wait('document.querySelectorAll(".record").length>=3');
 const covers=await c.evaluate('[...document.querySelectorAll(".record img")].map(x=>({alt:x.alt,width:x.naturalWidth,height:x.naturalHeight}))');
 assert(covers.every(x=>x.width===768&&x.height===768));record('Bundled covers displayed',covers);
 if(!process.env.REUSE_GENERATED){
 await c.click('[data-view="create"]');
 await c.evaluate(`(()=>{const values={topic:'Watching rain from a train window with a cup of tea, going home',title:'Window Seat — browser check',duration:'12','style-select':'custom','custom-style':'gentle acoustic folk with fingerpicked guitar','mood-select':'custom','custom-mood':'peaceful and hopeful','track-type':'vocal','cover-prompt':'A cup of tea by a rainy train window, softly rolling green hills outside'};for(const[id,value]of Object.entries(values)){const e=document.getElementById(id);e.value=value;e.dispatchEvent(new Event('change',{bubbles:true}));}})()`);
 assert(await c.evaluate('document.getElementById("generate").disabled'));
 await c.click('#draft-lyrics');
 await c.wait('document.getElementById("lyrics").value.length>0 && !document.getElementById("draft-lyrics").disabled',180000);
 const original=await c.evaluate('document.getElementById("lyrics").value');
 await c.evaluate(`(()=>{const e=document.getElementById('lyrics');e.value+= '\\nHome is waiting past the rain.';e.dispatchEvent(new Event('input',{bubbles:true}));})()`);
 const edited=await c.evaluate('document.getElementById("lyrics").value');assert.notEqual(edited,original);
 await c.screenshot('docs/screenshots/lyrics-review.png');
 await c.click('#generate');
 await c.wait('!document.getElementById("library-view").hidden');
 const id=await c.evaluate(`(async()=>{const a=await(await fetch('/api/songs')).json();return a.find(x=>x.title==='Window Seat — browser check').id;})()`);
 await c.wait(`document.querySelector('[data-song-id="${id}"] .record-status')`,10000);
 await c.screenshot('docs/screenshots/generating.png');
 await c.wait(`(async()=>{const s=await(await fetch('/api/songs/${id}')).json();if(s.status==='failed')throw Error(s.error);return s.status==='ready'&&s.cover_status==='ready';})()`,600000);
 const generated=await c.evaluate(`(async()=>{const s=await(await fetch('/api/songs/${id}')).json();return {id:s.id,status:s.status,cover:s.cover_status,duration:s.actual_duration,lyrics:s.lyrics,requested:s.duration};})()`);
 assert.equal(generated.lyrics,edited);assert(Math.abs(generated.duration-12)<1);record('Qwen lyrics reviewed and edited; ACE+FLUX saved',generated);
 await c.wait(`document.querySelector('[data-song-id="${id}"] .play-record')`);
 }
 // Start this scenario with an empty queue: reload preserves the tab's queue,
 // and browser_extra intentionally leaves Amber queued to verify persistence.
 await c.click('#clear-queue');
 assert.deepEqual(await c.evaluate('jukebox.player.queue.map(s=>s.id)'),[]);
 // Exercise real speech, pause while awaiting Qwen/Chatterbox, then natural transition.
 if(await c.evaluate('!document.getElementById("notice").hidden'))await c.click('#dismiss-notice');
 await c.click(`[data-song-id="sample-amber-after-hours"] .play-record`);
 await c.wait('jukebox.player.phase==="loading"');
 await c.click('#play-pause');
 await c.wait('jukebox.player.phase==="speech"',180000);
 assert(await c.evaluate('jukebox.player.paused&&document.getElementById("audio").paused'));
 record('Pause while live DJ request runs preserved',await c.evaluate('({phase:jukebox.player.phase,paused:jukebox.player.paused,intro:jukebox.player.intro})'));
 await c.click('#play-pause');
 await c.wait('document.getElementById("audio").currentTime>0.1');
 await c.screenshot('docs/screenshots/dj-playing.png');
 await c.click(`[data-song-id="sample-saturday-neon"] .record-actions button:nth-child(2)`);
 await c.wait('jukebox.player.phase==="music"',90000);
 const first=await c.evaluate('({phase:jukebox.player.phase,id:jukebox.player.current.id,src:document.getElementById("audio").currentSrc,paused:document.getElementById("audio").paused})');
 assert.equal(first.id,'sample-amber-after-hours');assert(!first.paused);record('Natural speech-to-song transition',first);
 await c.wait('jukebox.player.current?.id==="sample-saturday-neon"',60000);
 record('Natural audio ended advanced independent queue',await c.evaluate('({phase:jukebox.player.phase,id:jukebox.player.current.id,queue:jukebox.player.queue.length})'));
 await c.click('#skip');
 await c.wait('jukebox.player.phase==="music"');
 assert.equal(await c.evaluate('jukebox.player.current.id'),'sample-saturday-neon');
 await c.sleep(1500);assert.equal(await c.evaluate('jukebox.player.phase'),'music');record('Skip pending DJ starts associated song, no stale takeover',true);
 await c.click('#play-pause');
 await c.click('[data-view="dj"]');await c.screenshot('docs/screenshots/dj-booth.png');
 await c.click('[data-view="library"]');
 await c.screenshot('docs/screenshots/mobile.png',390,844);
 assert.equal(await c.evaluate('document.documentElement.scrollWidth>innerWidth'),false);record('Mobile horizontal overflow',false);
 await c.screenshot('docs/screenshots/collection-after-generation.png');
 record('Uncaught browser exceptions',c.errors);assert.equal(c.errors.length,0);
}finally{c.close();}
