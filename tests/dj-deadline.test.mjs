// Offline deterministic deadlines, with real player code and a manually driven clock.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

function setup(requestDJ=()=>new Promise(()=>{})) {
  const timers=new Map(), revoked=[], notes=[];let serial=0,signal;
  const context=vm.createContext({AbortController,URL:{revokeObjectURL:url=>revoked.push(url)},
    setTimeout:(fn,ms)=>{const id=++serial;timers.set(id,{fn,ms});return id;},
    clearTimeout:id=>timers.delete(id)});
  vm.runInContext(fs.readFileSync(new URL('../jukebox/static/player.js',import.meta.url),'utf8'),context);
  const audio={src:'',paused:true,plays:0,pause(){this.paused=true;},async play(){this.paused=false;this.plays++;}};
  const player=new context.JukeboxPlayer({audio,requestDJ:(song,s)=>{signal=s;return requestDJ(song,s);},notice:n=>notes.push(n),onChange:()=>{}});
  player.enqueue({id:'a',title:'A'});
  return {player,audio,timers,revoked,notes,get signal(){return signal;},expire(){for(const {fn} of [...timers.values()])fn();}};
}
const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};

for(const action of ['timeout','skip','pause-timeout','timeout-skip-next']) {
  test(`late DJ resolution after ${action} cannot replace music and releases its blob`,async()=>{
    let resolve;const h=setup(()=>new Promise(r=>resolve=r));
    const pending=h.player.next();
    if(action==='pause-timeout')await h.player.toggle();
    if(action==='skip')await h.player.skip();else {h.expire();await flush();}
    if(action==='timeout-skip-next') {
      h.player.dj=false;h.player.enqueue({id:'b',title:'B'});await h.player.skip();
    }
    await pending;
    const src=h.audio.src,plays=h.audio.plays;
    resolve({url:'blob:late-private-speech',intro:'Must not be spoken'});await flush();
    assert.equal(h.player.phase,'music');assert.equal(h.audio.src,src);
    assert.equal(h.audio.plays,plays);assert.equal(h.player.intro,'');
    assert.deepEqual(h.revoked,['blob:late-private-speech']);
    assert.equal(h.timers.size,0);assert.equal(h.signal.aborted,true);
    if(action==='pause-timeout') {
      assert.equal(h.player.paused,true);assert.equal(h.audio.paused,true);assert.equal(plays,0);
      await h.player.toggle();assert.equal(h.audio.plays,1);
    }
    assert.equal(h.notes.length,action==='skip'?0:1);
  });
}

for(const action of ['timeout','skip']) {
  test(`DJ resolving in same turn as ${action} releases its blob`,async()=>{
    let resolve;const h=setup(()=>new Promise(r=>resolve=r));const pending=h.player.next();
    // Resolve queues a microtask; cancellation wins before that task runs.
    resolve({url:'blob:same-turn',intro:'Late'});
    if(action==='timeout')h.expire();else h.player.skip();
    await pending;await flush();
    assert.equal(h.player.phase,'music');assert.equal(h.audio.plays,1);
    assert.deepEqual(h.revoked,['blob:same-turn']);assert.equal(h.timers.size,0);
  });
}

for(const outcome of ['success','failure','skip','next','disable']) {
  test(`DJ timer is cleaned up on ${outcome}`,async()=>{
    const h=setup(outcome==='success'?async()=>({url:'/intro.mp3',intro:'Welcome'}):
      outcome==='failure'?async()=>{throw Error('fixture failure');}:undefined);
    const pending=h.player.next();
    if(outcome==='skip')await h.player.skip();
    if(outcome==='next')await h.player.next();
    if(outcome==='disable')h.player.setDJ(false);
    await pending;
    assert.equal(h.timers.size,0);
    const phase=h.player.phase,plays=h.audio.plays;
    h.expire();await flush();
    assert.equal(h.player.phase,phase);assert.equal(h.audio.plays,plays);
    if(outcome==='success')assert.equal(h.signal.aborted,false);
  });
}

test('never-resolving DJ aborts at 20 seconds and starts music exactly once',async()=>{
  const h=setup();const pending=h.player.next();
  assert.equal(h.player.phase,'loading');
  assert.deepEqual([...h.timers.values()].map(t=>t.ms),[20000]);
  h.expire();await flush();
  assert.equal(h.signal.aborted,true);
  assert.equal(h.player.phase,'music');assert.equal(h.audio.src,'/api/songs/a/audio');
  assert.equal(h.audio.plays,1);assert.match(h.notes[0],/timed out/);
  assert.equal(h.timers.size,0);await pending;
});
