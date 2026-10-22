// Controlled regression, NOT an upstream health probe. Requires a separate
// headless Chrome on CDP_PORT (default 9231) and local Jukebox on APP_URL.
// Creates/closes its own tab; intercepts DJ before it can reach the server.
import assert from 'node:assert/strict';
const cdpBase=`http://127.0.0.1:${process.env.CDP_PORT||9231}`;
const appURL=process.env.APP_URL||'http://127.0.0.1:8765';
const target=await (await fetch(`${cdpBase}/json/new?about:blank`,{method:'PUT'})).json();
const ws=new WebSocket(target.webSocketDebuggerUrl);
let serial=0,intercepted=0;const pending=new Map(),errors=[];
ws.onmessage=e=>{
  const m=JSON.parse(e.data);
  if(m.id&&pending.has(m.id)) {const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(m.error.message)):p.resolve(m.result);}
  if(m.method==='Fetch.requestPaused')intercepted++; // Deliberately never continue.
  if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);
};
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
const evaluate=async expression=>{
  const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
  if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);
  return r.result.value;
};
const wait=async expression=>{
  const end=Date.now()+5000;
  while(Date.now()<end){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,25));}
  throw Error(`Timed out: ${expression}`);
};
try {
  await send('Page.enable');await send('Runtime.enable');
  await send('Fetch.enable',{patterns:[{urlPattern:appURL+'/api/dj/*',requestStage:'Request'}]});
  await send('Page.addScriptToEvaluateOnNewDocument',{source:`
    (()=>{
      const timers=new Map();let serial=0;
      const nativeSet=window.setTimeout.bind(window),nativeClear=window.clearTimeout.bind(window),nativeFetch=window.fetch.bind(window);
      window.__djDeadlineTest={timers,aborted:false,delays:[],fire(){for(const fn of [...timers.values()])fn();}};
      window.setTimeout=(fn,ms,...args)=>{
        if(ms!==20000)return nativeSet(fn,ms,...args);
        const id=--serial;timers.set(id,()=>fn(...args));window.__djDeadlineTest.delays.push(ms);return id;
      };
      window.clearTimeout=id=>{if(timers.has(id))timers.delete(id);else nativeClear(id);};
      window.fetch=(url,options)=>{
        if(String(url).startsWith('/api/dj/'))options.signal.addEventListener('abort',()=>{window.__djDeadlineTest.aborted=true;},{once:true});
        return nativeFetch(url,options);
      };
    })();
  `});
  await send('Page.navigate',{url:appURL});
  await wait("window.jukebox && document.querySelector('[data-song-id^=\"sample-\"] .play-record')");
  await evaluate(`(()=>{document.getElementById('audio').muted=true;document.querySelector('[data-song-id^="sample-"] .play-record').click();})()`);
  await wait("window.jukebox.player.phase==='loading' && window.__djDeadlineTest.timers.size===1");
  // Give CDP a chance to deliver the intercepted-request event before expiry.
  const end=Date.now()+5000;
  while(intercepted===0&&Date.now()<end)await new Promise(r=>setTimeout(r,25));
  assert.equal(intercepted,1);
  const before=await evaluate("({phase:jukebox.player.phase,label:document.getElementById('now-phase').textContent,delays:__djDeadlineTest.delays})");
  assert.deepEqual(before.delays,[20000]);
  await evaluate('__djDeadlineTest.fire()');
  await wait("jukebox.player.phase==='music' && !document.getElementById('audio').paused && document.getElementById('audio').currentTime>0");
  const after=await evaluate(`({phase:jukebox.player.phase,label:document.getElementById('now-phase').textContent,aborted:__djDeadlineTest.aborted,timers:__djDeadlineTest.timers.size,notice:document.getElementById('notice-text').textContent,playing:!document.getElementById('audio').paused,advanced:document.getElementById('audio').currentTime>0})`);
  assert.equal(after.aborted,true);assert.equal(after.timers,0);assert.match(after.notice,/timed out/);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({test:'controlled stalled DJ fetch; manually fired 20s timer',intercepted,before,after,uncaughtErrors:errors},null,2));
}finally {
  await fetch(`${cdpBase}/json/close/${target.id}`);ws.close();
}
