// Real Chrome CDP helper. Optional developer verification; not needed to run Jukebox.
import fs from 'node:fs';
export async function connect(){
  const targets=await (await fetch('http://127.0.0.1:9227/json/list')).json();
  const target=targets.find(t=>t.type==='page'&&t.url.startsWith('http://127.0.0.1:8765'));
  if(!target)throw Error('Launch headless Chrome on port 9227 at http://127.0.0.1:8765 first.');
  const ws=new WebSocket(target.webSocketDebuggerUrl);let id=0;const pending=new Map();const errors=[];
  ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}else if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);};
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}));});
  const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const wait=async(expression,timeout=30000)=>{const end=Date.now()+timeout;while(Date.now()<end){if(await evaluate(expression))return;await sleep(250);}throw Error('Timed out: '+expression);};
  const click=async selector=>{const r=await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...r});await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...r});};
  const screenshot=async(path,width=1440,height=960)=>{await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600});await sleep(300);const s=await send('Page.captureScreenshot',{format:'png'});fs.mkdirSync(new URL('../docs/screenshots/',import.meta.url),{recursive:true});fs.writeFileSync(path,Buffer.from(s.data,'base64'));};
  await send('Page.enable');await send('Runtime.enable');
  return {send,evaluate,wait,click,screenshot,sleep,errors,close:()=>ws.close()};
}
