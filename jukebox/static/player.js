/* One audio element, one generation token, one playback intent per browser tab. */
class JukeboxPlayer {
  constructor({audio,requestDJ,onChange,notice}) {
    Object.assign(this,{audio,requestDJ,onChange,notice});
    this.queue=[]; this.current=null; this.phase='idle'; this.paused=true;
    this.dj=true; this.token=0; this.playAttempt=0; this.controller=null; this.blob=null; this.intro='';
  }
  changed(){this.onChange(this);}
  enqueue(song){this.queue.push(song);this.changed();}
  remove(index){this.queue.splice(index,1);this.changed();}
  clear(){this.queue=[];this.changed();}
  invalidate(){
    this.token++;this.controller?.abort();this.controller=null;
    this.audio.pause();this.audio.onended=null;this.audio.onerror=null;
    if(this.blob){URL.revokeObjectURL(this.blob);this.blob=null;}
    return this.token;
  }
  async prepareDJ(song,controller){
    let timer,onAbort,settled=false;
    const deadline=new Promise((_,reject)=>{
      onAbort=()=>reject(Error('DJ request cancelled'));
      controller.signal.addEventListener('abort',onAbort,{once:true});
      timer=setTimeout(()=>{
        reject(Error('DJ preparation timed out'));
        controller.abort();
      },20000);
    });
    try{
      // Race as well as abort: even a request that ignores cancellation must
      // release the player. The budget covers the entire fetch/decode callback.
      const request=this.requestDJ(song,controller.signal).then(result=>{
        // A non-cooperative request may create a private speech blob after
        // cancellation. It must neither play nor retain that late URL.
        if((settled||controller.signal.aborted)&&result.url?.startsWith('blob:'))URL.revokeObjectURL(result.url);
        return result;
      });
      return await Promise.race([request,deadline]);
    }finally{
      settled=true;clearTimeout(timer);controller.signal.removeEventListener('abort',onAbort);
    }
  }
  async next(){
    const token=this.invalidate();this.current=this.queue.shift()||null;this.intro='';
    if(!this.current){this.phase='idle';this.paused=true;this.changed();return;}
    this.paused=false;
    if(!this.dj){await this.music(token);return;}
    this.phase='loading';this.changed();this.controller=new AbortController();
    try{
      const result=await this.prepareDJ(this.current,this.controller);
      if(token!==this.token){if(result.url?.startsWith('blob:'))URL.revokeObjectURL(result.url);return;}
      this.intro=result.intro;this.blob=result.url.startsWith('blob:')?result.url:null;
      await this.source(result.url,'speech',token);
    }catch(e){
      if(token!==this.token)return;
      this.notice(`DJ unavailable: ${e.message}. Continuing with music.`);
      await this.music(token);
    }
  }
  async music(token=this.token){
    if(token!==this.token||!this.current)return;
    await this.source(`/api/songs/${this.current.id}/audio`,'music',token);
  }
  async source(url,phase,token){
    if(token!==this.token)return;
    this.audio.pause();this.audio.src=url;this.phase=phase;
    this.audio.onended=()=>{
      if(token!==this.token||this.paused)return;
      if(phase==='speech')this.music(token);else this.next();
    };
    this.audio.onerror=()=>{
      if(token!==this.token)return;
      if(phase==='speech'){this.notice('DJ audio could not play. Continuing with music.');this.music(token);}
      else{this.paused=true;this.notice('This audio could not play. Try Play again or Skip to the next track.');this.changed();}
    };
    if(!this.paused)await this.safePlay(token);
    this.changed();
  }
  async safePlay(token){
    const attempt=++this.playAttempt,phase=this.phase,src=this.audio.src;
    try{await this.audio.play();}
    catch(e){
      if(attempt!==this.playAttempt||token!==this.token||phase!==this.phase||src!==this.audio.src)return;
      this.paused=true;
      this.notice(e.name==='NotSupportedError'?'This audio could not play. Try Play again or Skip to the next track.':'Your browser paused playback. Press Play to continue.');
    }
  }
  async toggle(){
    if(!this.current){await this.next();return;}
    this.paused=!this.paused;
    if(this.paused){this.playAttempt++;this.audio.pause();}
    else if(this.phase!=='loading')await this.safePlay(this.token);
    this.changed();
  }
  async skip(){
    if(this.current&&['loading','speech'].includes(this.phase)){
      const token=this.invalidate();await this.music(token);
    }else await this.next();
  }
  setDJ(enabled){
    this.dj=enabled;
    if(!enabled&&['loading','speech'].includes(this.phase))this.skip();
    this.changed();
  }
}
globalThis.JukeboxPlayer=JukeboxPlayer;
