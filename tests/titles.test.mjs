// Actual application form and library rendering, offline DOM doubles.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
function setup(){
  const elements=new Map();
  function node(){return {value:'',textContent:'',children:[],classList:{toggle(){}},setAttribute(k,v){this[k]=v;},append(c){this.children.push(c);},replaceChildren(...c){this.children=c;}};}
  const element=id=>{if(!elements.has(id))elements.set(id,node());return elements.get(id);};
  const context=vm.createContext({document:{getElementById:element,querySelectorAll:()=>[],createElement:node},window:{},JukeboxPlayer:class{},fetch:()=>new Promise(()=>{}),setInterval(){}});
  vm.runInContext(fs.readFileSync(new URL('../jukebox/static/app.js',import.meta.url),'utf8'),context);
  return {context,element};
}
test('blank title stays blank rather than copying topic, explicit title stays chosen',()=>{
  const {context,element}=setup();element('topic').value='A long descriptive topic';
  assert.equal(vm.runInContext('spec().title',context),'');
  element('title').value='My chosen title';assert.equal(vm.runInContext('spec().title',context),'My chosen title');
});


for(const state of ['pending','generating','fallback'])test(`library shows honest ${state} title state safely`,()=>{
  const {context,element}=setup();element('filter').value='all';
  context.fixture={id:'test',title:'<b>Literal name</b>',topic:'Rain',style:'Jazz',duration:30,instrumental:true,
    status:state==='fallback'?'ready':'generating',cover_status:'ready',title_status:state,title_error:'Automatic title unavailable. Using Untitled track.'};
  vm.runInContext('songs=[fixture];renderLibrary()',context);
  const card=element('library').children[0];
  assert.equal(card.children.find(c=>c.textContent==='<b>Literal name</b>').children.length,0);
  const text=card.children.map(c=>c.textContent).join(' ');
  assert.match(text,state==='fallback'?/Automatic title unavailable/:state==='pending'?/title.*queued/i:/Qwen.*title/i);
  if(state==='generating')assert.doesNotMatch(text,/Creating your music/);
});
test('form explains contextual titles instead of topic copying',()=>{
  const html=fs.readFileSync(new URL('../jukebox/static/index.html',import.meta.url),'utf8');
  assert.doesNotMatch(html,/otherwise we use your topic/);
  assert.match(html,/optional — Qwen creates a contextual title/);
});
