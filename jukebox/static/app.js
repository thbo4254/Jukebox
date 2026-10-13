'use strict';
const $=id=>document.getElementById(id);
const audio=$('audio');audio.volume=.8;
let songs=[],lastLibrary='',reference=null,voiceSelection=0,drafting=false,submitting=false;
function notice(message){$('notice-text').textContent=message;$('notice').hidden=false;}
$('dismiss-notice').onclick=()=>{$('notice').hidden=true;};
async function api(path,body,signal){
  let r;
  try{r=await fetch(path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-Jukebox':'1'},body:body===undefined?undefined:JSON.stringify(body),signal});}
  catch(e){if(e.name==='AbortError')throw e;throw Error('The local app is unreachable. Keep the Python server running and try again.');}
  const data=await r.json();if(!r.ok)throw Error(data.detail||'The request could not be completed. Please retry.');return data;
}
function make(tag,props={},children=[]){
  const e=document.createElement(tag);for(const[k,v]of Object.entries(props)){if(k==='text')e.textContent=v;else if(k==='class')e.className=v;else e.setAttribute(k,v);}for(const c of children)e.append(c);return e;
}
function button(text,click,cls=''){const b=make('button',{text,class:cls});b.onclick=click;return b;}
function art(song){return song?.cover_status==='ready'?`/api/songs/${song.id}/cover`:'/static/placeholder.svg';}
function clock(n){if(!Number.isFinite(n))return '0:00';return `${Math.floor(n/60)}:${String(Math.floor(n%60)).padStart(2,'0')}`;}
function show(view){
  for(const name of ['library','create','dj'])$(name+'-view').hidden=view!==name;
  document.querySelectorAll('nav [data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===view);if(b.dataset.view===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>show(b.dataset.view));
const player=new JukeboxPlayer({audio,notice,onChange:renderPlayer,requestDJ:async(song,signal)=>{
  const d=await api('/api/dj/'+song.id,{personality:$('personality').value,reference},signal);
  const bytes=Uint8Array.from(atob(d.audio),c=>c.charCodeAt(0));
  return {intro:d.intro,url:URL.createObjectURL(new Blob([bytes],{type:'audio/mpeg'}))};
}});
window.jukebox={player}; // Useful for local diagnostics; contains no server configuration or credentials.
function renderPlayer(){
  $('queue').replaceChildren(...player.queue.map((s,i)=>make('li',{},[make('img',{src:art(s),alt:''}),make('span',{text:s.title}),button('×',()=>player.remove(i))])));
  [...$('queue').querySelectorAll('button')].forEach((b,i)=>b.setAttribute('aria-label','Remove '+player.queue[i].title+' from queue'));
  $('queue-empty').hidden=player.queue.length>0;$('queue-count').textContent=player.queue.length;
  try{sessionStorage.setItem('jukebox-queue',JSON.stringify(player.queue.map(s=>s.id)));}catch{}
  $('play-pause').textContent=player.paused?'Play':'Pause';$('play-pause').setAttribute('aria-label',player.paused?'Play':'Pause');
  const phases={idle:'READY WHEN YOU ARE',loading:'YOUR DJ IS GETTING READY',speech:'ON AIR · DJ INTRO',music:'NOW SPINNING'};
  $('now-phase').textContent=(player.paused&&player.current?'PAUSED · ':'')+phases[player.phase];
  $('now-title').textContent=player.current?.title||'Put something good on.';
  $('now-detail').textContent=player.intro||player.current?.style||'Choose a record to start listening.';
  $('now-cover').src=art(player.current);$('now-cover').alt=player.current?'Cover for '+player.current.title:'Record placeholder';
}
$('play-pause').onclick=()=>player.toggle();$('skip').onclick=()=>player.skip();$('clear-queue').onclick=()=>player.clear();
$('volume').oninput=()=>audio.volume=Number($('volume').value);
audio.ontimeupdate=()=>{$('clock').textContent=clock(audio.currentTime)+' / '+clock(audio.duration);};
function details(song){
  $('details-title').textContent=song.title;$('details-about').textContent=`${song.style} · ${song.mood} · ${song.actual_duration?.toFixed(1)||song.duration} seconds. ${song.topic}`;
  $('details-lyrics').textContent=song.instrumental?'Instrumental — no lyrics.':song.lyrics;
  $('download-audio').href=`/api/songs/${song.id}/audio`;$('download-audio').download=song.title+'.mp3';$('details').showModal();
}
$('close-details').onclick=()=>$('details').close();
async function retry(song,cover){try{await api(`/api/songs/${song.id}/${cover?'retry-cover':'retry'}`,{});await refresh();}catch(e){notice(e.message);}}
function renderLibrary(){
  const search=$('search').value.toLowerCase(),filter=$('filter').value;
  const shown=songs.filter(s=>(filter==='all'||s.instrumental===(filter==='instrumental'))&&`${s.title} ${s.topic} ${s.style}`.toLowerCase().includes(search));
  $('record-count').textContent=songs.length+' records';$('empty').hidden=shown.length>0;
  $('library').replaceChildren(...shown.map(s=>{
    const cover=make('div',{class:'cover-wrap'},[make('img',{src:art(s),alt:`Cover for ${s.title}`,loading:'lazy'}),make('span',{class:'record-type',text:s.instrumental?'INSTRUMENTAL':'VOCAL'})]);
    const meta=make('p',{class:'record-meta',text:`${s.style} · ${s.actual_duration?Math.round(s.actual_duration):s.duration}s${s.sample?' · Original sample':''}`});
    const actions=make('div',{class:'record-actions'});
    if(s.status==='ready'){
      actions.append(button('Play',()=>{player.queue.unshift(s);player.next();},'play-record'),button('+ Queue',()=>{player.enqueue(s);notice(`${s.title} added to your queue.`);}),button('Details',()=>details(s)));
      if(s.cover_status==='failed')actions.append(button('Retry cover',()=>retry(s,true)));
    }else if(s.status==='failed')actions.append(button('Retry song',()=>retry(s,false),'secondary'));
    const card=make('article',{class:'record','data-song-id':s.id},[cover,make('h2',{text:s.title}),meta,actions]);
    if(s.status!=='ready')card.append(make('p',{class:s.status==='failed'?'record-error':'record-status',text:s.status==='failed'?s.error:s.status==='queued'?'Waiting for the studio…':'Creating your music…'}));
    if(s.status==='ready'&&s.cover_status!=='ready')card.append(make('p',{class:s.cover_status==='failed'?'record-error':'record-status',text:s.cover_status==='failed'?s.cover_error:'Your music is ready. Painting the cover…'}));
    return card;
  }));
}
$('search').oninput=renderLibrary;$('filter').onchange=renderLibrary;
$('play-collection').onclick=()=>{player.queue=songs.filter(s=>s.status==='ready');player.next();};
async function refresh(){
  const data=await api('/api/songs');songs=data;
  const stamp=JSON.stringify(songs);if(stamp!==lastLibrary){lastLibrary=stamp;renderLibrary();}
}
function choice(name){return $(name+'-select').value==='custom'?$('custom-'+name).value:$(name+'-select').value;}
function spec(){
  return {title:$('title').value.trim()||$('topic').value.trim().slice(0,60),topic:$('topic').value,style:choice('style'),mood:choice('mood'),duration:Number($('duration').value),instrumental:$('track-type').value==='instrumental',lyrics:$('lyrics').value,cover_prompt:$('cover-prompt').value};
}
for(const name of ['style','mood'])$(name+'-select').onchange=()=>{const custom=$(name+'-select').value==='custom';$('custom-'+name).hidden=!custom;$('custom-'+name).required=custom;};
function updateForm(){
  const vocal=$('track-type').value==='vocal';$('vocal-controls').hidden=!vocal;
  $('generate').disabled=submitting||drafting||(vocal&&!$('lyrics').value.trim());
  $('draft-lyrics').disabled=drafting||submitting;
}
$('track-type').onchange=updateForm;$('lyrics').oninput=updateForm;
$('draft-lyrics').onclick=async()=>{
  if(!$('song-form').reportValidity())return;
  drafting=true;updateForm();$('form-status').textContent='Qwen is writing your lyrics…';
  try{const d=await api('/api/lyrics',spec());$('lyrics').value=d.lyrics;$('review-label').hidden=false;$('form-status').textContent='Review and edit, then generate your record.';$('lyrics').focus();}
  catch(e){notice(e.message);$('form-status').textContent='Lyrics failed. You can try again.';}
  finally{drafting=false;updateForm();}
};
$('song-form').onsubmit=async e=>{
  e.preventDefault();if(submitting||drafting)return;
  submitting=true;updateForm();$('form-status').textContent='Sending your record to the studio…';
  try{await api('/api/songs',spec());$('form-status').textContent='Your song is in the studio.';await refresh();show('library');notice('Your song is queued. Keep the Python app running; your record will appear here when ready.');}
  catch(e){notice(e.message);$('form-status').textContent='Not submitted. Check the notice and try again.';}
  finally{submitting=false;updateForm();}
};
$('dj-enabled').onchange=()=>{player.setDJ($('dj-enabled').checked);$('dj-summary').textContent=player.dj?$('personality').value:'Music only';};
$('personality').onchange=()=>{$('dj-summary').textContent=player.dj?$('personality').value:'Music only';};
$('voice').onchange=async()=>{
  const selection=++voiceSelection;reference=null;const file=$('voice').files[0];
  $('voice-status').textContent='Using the default voice.';
  if(!file)return;
  if(!/\.(mp3|wav)$/i.test(file.name)||file.size>=6*1024*1024){notice('Choose an MP3 or WAV recording under 6 MB.');$('voice').value='';$('voice-status').textContent='Using the default voice.';return;}
  let data;
  try{data=await file.arrayBuffer();}
  catch{
    if(selection!==voiceSelection)return;
    reference=null;$('voice').value='';$('voice-status').textContent='Using the default voice.';
    notice('Could not read that recording. Choose it again or use the default voice.');return;
  }
  if(selection!==voiceSelection)return;
  let binary='';for(const b of new Uint8Array(data))binary+=String.fromCharCode(b);
  reference=btoa(binary);$('voice-status').textContent=`${file.name} · temporary reference. Cleared on refresh.`;
};
$('clear-voice').onclick=()=>{voiceSelection++;reference=null;$('voice').value='';$('voice-status').textContent='Using the default voice.';};
async function boot(){
  try{
    const status=await api('/api/status');$('connection').textContent=status.configured?'LOCAL LIBRARY · CLASS SERVICES':'CONFIGURATION NEEDED';
    $('connection').classList.toggle('warning',!status.configured);if(!status.configured)notice(status.message);
    await refresh();
    try{const ids=JSON.parse(sessionStorage.getItem('jukebox-queue')||'[]');player.queue=ids.map(id=>songs.find(s=>s.id===id&&s.status==='ready')).filter(Boolean);}catch{}
    renderPlayer();
  }catch(e){notice(e.message);$('connection').textContent='APP UNREACHABLE';}
  setInterval(()=>refresh().catch(e=>notice(e.message)),3000);
}
updateForm();boot();
