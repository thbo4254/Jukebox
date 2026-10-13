// Extra real-browser checks: upload, invalid upload recovery, tab isolation, native media controls.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {connect} from './cdp.mjs';
const c=await connect();const evidence=[];const reference='/tmp/jukebox-synthetic-reference.mp3';
function record(name,result){evidence.push({name,result});console.log(name,JSON.stringify(result));fs.writeFileSync('docs/evidence/browser-extra.json',JSON.stringify(evidence,null,2));}
try{
 await c.send('Page.reload',{ignoreCache:true});await c.sleep(500);await c.wait('document.querySelectorAll(".record").length>=3');
 const r=await fetch('http://127.0.0.1:8765/api/dj/sample-amber-after-hours',{method:'POST',headers:{'X-Jukebox':'1','Content-Type':'application/json'},body:JSON.stringify({personality:'Warm & Laid-back'})});
 assert.equal(r.status,200);const d=await r.json();fs.writeFileSync(reference,Buffer.from(d.audio,'base64'));
 await c.click('[data-view="dj"]');
 await c.evaluate(`(()=>{const orig=window.fetch;window.fetch=(url,options)=>{if(String(url).startsWith('/api/dj/'))window.referenceWasSent=!!JSON.parse(options.body).reference;return orig(url,options);};document.getElementById('personality').value='Upbeat & Playful';document.getElementById('personality').dispatchEvent(new Event('change'));})()`);
 const doc=await c.send('DOM.getDocument');const {nodeId}=await c.send('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#voice'});
 await c.send('DOM.setFileInputFiles',{nodeId,files:[reference]});
 await c.wait('document.getElementById("voice-status").textContent.includes("temporary reference")');
 await c.screenshot('docs/screenshots/voice-reference.png');
 await c.click('[data-view="library"]');await c.click('[data-song-id="sample-the-long-way-home"] .play-record');
 await c.wait('jukebox.player.phase==="speech"',180000);
 await c.wait('document.getElementById("audio").currentTime>0.1',30000);
 assert(await c.evaluate('window.referenceWasSent===true'));
 record('Actual MP3 upload -> Chatterbox reference speech -> browser playback',{synthetic:true,phase:await c.evaluate('jukebox.player.phase'),intro:await c.evaluate('jukebox.player.intro')});
 await c.click('#skip');await c.wait('jukebox.player.phase==="music"&&!document.getElementById("audio").paused');
 await c.click('#play-pause');const before=await c.evaluate('document.getElementById("audio").currentTime');await c.sleep(500);
 assert.equal(await c.evaluate('document.getElementById("audio").paused'),true);
 assert(Math.abs(await c.evaluate('document.getElementById("audio").currentTime')-before)<.1);
 await c.click('#play-pause');await c.wait(`document.getElementById('audio').currentTime>${before+.2}`);record('Music pause freezes playback, Play resumes',true);
 await c.click('#play-pause');await c.click('[data-view="dj"]');await c.click('#clear-voice');
 assert.equal(await c.evaluate('document.getElementById("voice").files.length'),0);record('Use default voice clears file control',true);
 // Invalid but correctly named WAV is rejected server-side; music must still continue.
 fs.writeFileSync('/tmp/jukebox-invalid-reference.wav','intentionally invalid unit of browser failure evidence');
 await c.send('DOM.setFileInputFiles',{nodeId,files:['/tmp/jukebox-invalid-reference.wav']});
 await c.wait('document.getElementById("voice-status").textContent.includes("temporary reference")');
 await c.click('[data-view="library"]');await c.click('[data-song-id="sample-saturday-neon"] .play-record');
 await c.wait('jukebox.player.phase==="music"');
 const failure=await c.evaluate('({notice:document.getElementById("notice-text").textContent,paused:document.getElementById("audio").paused})');
 assert.match(failure.notice,/valid MP3 or WAV/);assert.equal(failure.paused,false);record('Invalid voice upload explains failure and continues real music',failure);
 await c.screenshot('docs/screenshots/recoverable-error.png');await c.click('#play-pause');
 await c.click('[data-song-id="sample-amber-after-hours"] .record-actions button:nth-child(2)');
 const beforeIds=await c.evaluate('jukebox.player.queue.map(s=>s.id)');assert(beforeIds.length>0);
 const {targetId}=await c.send('Target.createTarget',{url:'http://127.0.0.1:8765/'});
 const targets=await(await fetch('http://127.0.0.1:9227/json/list')).json();const target=targets.find(t=>t.id===targetId);
 const ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r);
 let id=0;const pending=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data);if(pending.has(m.id)){pending.get(m.id)(m.result);pending.delete(m.id);}};
 const ev=expr=>new Promise(resolve=>{const n=++id;pending.set(n,resolve);ws.send(JSON.stringify({id:n,method:'Runtime.evaluate',params:{expression:expr,returnByValue:true}}));});
 for(let i=0;i<40;i++){const x=await ev('window.jukebox?.player.queue.length');if(x.result?.value===0)break;await c.sleep(100);}
 assert.equal((await ev('jukebox.player.queue.length')).result.value,0);record('Second independent tab has its own empty queue',true);ws.close();await c.send('Target.closeTarget',{targetId});
 await c.send('Page.reload',{ignoreCache:true});await c.sleep(500);await c.wait('window.jukebox&&document.querySelectorAll(".record").length>=3');
 assert.equal(await c.evaluate('document.getElementById("voice").files.length'),0);record('Refresh discards voice; saved queue survives only in its tab',await c.evaluate('({voiceFiles:document.getElementById("voice").files.length,queue:jukebox.player.queue.map(s=>s.id)})'));
 record('Browser exceptions',c.errors);assert.equal(c.errors.length,0);
}finally{for(const path of [reference,'/tmp/jukebox-invalid-reference.wav'])if(fs.existsSync(path))fs.unlinkSync(path);c.close();}
