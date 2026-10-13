// Executes the actual app handlers with offline DOM/network doubles.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function setup(){
  const elements=new Map(),requests=[];
  const element=id=>{
    if(!elements.has(id))elements.set(id,{value:'',files:[],textContent:'',classList:{toggle(){}},setAttribute(){}});
    return elements.get(id);
  };
  const context=vm.createContext({
    document:{getElementById:element,querySelectorAll:()=>[]},window:{},
    JukeboxPlayer:class {constructor(options){Object.assign(this,options);}},
    fetch:async(path,options)=>{
      if(path==='/api/status')return new Promise(()=>{});
      requests.push(JSON.parse(options.body));
      return {ok:true,json:async()=>({audio:'',intro:'offline'})};
    },btoa,atob,Blob,URL,setInterval:()=>{},
  });
  vm.runInContext(fs.readFileSync(new URL('../jukebox/static/app.js',import.meta.url),'utf8'),context);
  return {element,select(name,read){element('voice').files=[{name,size:4,arrayBuffer:()=>read}];return element('voice').onchange();},
    async sentReference(){await context.window.jukebox.player.requestDJ({id:'fixture'});return requests.at(-1).reference;}};
}
test('clearing voice while its read is pending never sends the cleared reference',async()=>{
  const app=setup(),read=deferred();const pending=app.select('private.wav',read.promise);
  app.element('clear-voice').onclick();read.resolve(Uint8Array.of(1,2,3,4).buffer);await pending;
  assert.equal(await app.sentReference(),null);
  assert.equal(app.element('voice-status').textContent,'Using the default voice.');
});
test('newer voice selection wins even when the older read completes last',async()=>{
  const app=setup(),old=deferred(),latest=deferred();
  const first=app.select('old.wav',old.promise),second=app.select('latest.wav',latest.promise);
  latest.resolve(Uint8Array.of(5,6).buffer);await second;
  old.resolve(Uint8Array.of(1,2).buffer);await first;
  assert.equal(await app.sentReference(),'BQY=');
  assert.match(app.element('voice-status').textContent,/^latest.wav/);
});
test('failed voice read is handled and clears previous private reference and filename',async()=>{
  const app=setup();await app.select('previous.wav',Promise.resolve(Uint8Array.of(1).buffer));
  const read=deferred(),pending=app.select('unreadable.wav',read.promise);
  read.reject(Error('disk read failed'));await pending;
  assert.equal(await app.sentReference(),null);
  assert.equal(app.element('voice').value,'');
  assert.equal(app.element('voice-status').textContent,'Using the default voice.');
  assert.match(app.element('notice-text').textContent,/could not read/i);
});