// Live instrumental generation from the browser. Runtime output is ignored in /data.
import fs from 'node:fs';import assert from 'node:assert/strict';import {connect} from './cdp.mjs';
const c=await connect();try{
 await c.send('Page.reload',{ignoreCache:true});await c.sleep(500);await c.wait('window.jukebox&&document.querySelectorAll(".record").length>=3');
 await c.click('[data-view="create"]');
 await c.evaluate(`(()=>{window.calledEndpoints=[];const f=window.fetch;window.fetch=(u,o)=>{window.calledEndpoints.push(String(u));return f(u,o);};for(const[id,value]of Object.entries({topic:'A peaceful Sunday morning with coffee and rain on the windows',title:'Sunday Coffee — instrumental check',duration:'10','style-select':'Jazz trio','mood-select':'Warm & relaxed','track-type':'instrumental'})){const e=document.getElementById(id);e.value=value;e.dispatchEvent(new Event('change'));}})()`);
 assert(await c.evaluate('document.getElementById("vocal-controls").hidden&&!document.getElementById("generate").disabled'));
 await c.click('#generate');await c.wait('!document.getElementById("library-view").hidden');
 const id=await c.evaluate(`(async()=>{const s=await(await fetch('/api/songs')).json();return s.find(x=>x.title==='Sunday Coffee — instrumental check').id;})()`);
 await c.wait(`(async()=>{const s=await(await fetch('/api/songs/${id}')).json();if(s.status==='failed')throw Error(s.error);return s.status==='ready'&&s.cover_status==='ready';})()`,600000);
 assert.equal(await c.evaluate('window.calledEndpoints.includes("/api/lyrics")'),false);
 await c.wait(`document.querySelector('[data-song-id="${id}"] .play-record')`);
 await c.click('[data-view="dj"]');await c.click('#dj-enabled');await c.click('[data-view="library"]');await c.click(`[data-song-id="${id}"] .play-record`);
 await c.wait('jukebox.player.phase==="music"&&document.getElementById("audio").currentTime>.1');
 const result=await c.evaluate(`(async()=>{const s=await(await fetch('/api/songs/${id}')).json();return {id:s.id,instrumental:s.instrumental,lyrics:s.lyrics,duration:s.actual_duration,status:s.status,cover_status:s.cover_status,phase:jukebox.player.phase,paused:document.getElementById('audio').paused,lyricsEndpointCalled:window.calledEndpoints.includes('/api/lyrics')};})()`);
 assert.equal(result.duration,10);assert.equal(result.lyrics,'');assert.equal(result.paused,false);
 fs.writeFileSync('docs/evidence/instrumental-browser.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 await c.click('#play-pause');await c.screenshot('docs/screenshots/instrumental-generated.png');
}finally{c.close();}
