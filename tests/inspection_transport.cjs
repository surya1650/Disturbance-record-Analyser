'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const model=require('../src/dranalyser/application/static/inspection-model.js');
function fixture(n,channels=null){
  const nodes=new Map();
  function node(key){if(!nodes.has(key))nodes.set(key,{innerHTML:'',textContent:'',dataset:{},focus(){}});return nodes.get(key);}
  const mount={querySelector:node,querySelectorAll(selector){
    if(selector==='[data-pin]')return [...node('.inspection-pins').innerHTML.matchAll(/data-pin="([^\"]+)"/g)].map(m=>{const el=node('pin:'+m[1]);el.dataset.pin=m[1];return el;});
    if(selector==='[data-remove-pin]')return [...node('.inspection-pins').innerHTML.matchAll(/data-remove-pin="([^\"]+)"/g)].map(m=>{const el=node('remove:'+m[1]);el.dataset.removePin=m[1];return el;});
    return [];
  },scrollIntoView(){}};
  const host={isConnected:true,querySelector(){return mount}};
  const record={file:'x.cfg',revision:1,sample_count:n,source_sha256:{'x.cfg':'aaa'},inventory:[],time_basis:{},
    channels:channels||[{id:'A1',label:'A',kind:'analog',units:'raw counts',trace:[]},{id:'D1',label:'D',kind:'digital',units:'state',trace:[]}]};
  const calls=[],controller=new AbortController();
  let pointReply=null;
  const context=vm.createContext({DRInspection:model,DRTransport:require('../src/dranalyser/application/static/inspection-transport.js'),DRReadings:require('../src/dranalyser/application/static/inspection-readings.js'),escapeHtml:String,AbortController,URLSearchParams,setTimeout,clearTimeout,
    fetch:async url=>{
      calls.push(url);const q=new URL('http://localhost'+url).searchParams;
      if(url.includes('/points?')){
        if(pointReply)return pointReply();
        const indices=JSON.parse(q.get('indices'));
        return {ok:true,json:async()=>({file:'x.cfg',revision:1,source_sha256:{'x.cfg':'aaa'},channels:JSON.parse(q.get('channel_ids')).map(id=>({id,samples:indices.map(i=>[i,null,id==='D1'?0:i])}))})};
      }
      const id=q.get('channel_id'),lo=Number(q.get('start_index')),hi=Number(q.get('stop_index'));
      return {ok:true,json:async()=>({file:'x.cfg',revision:1,source_sha256:{'x.cfg':'aaa'},channel_id:id,samples:Array.from({length:hi-lo},(_,k)=>[lo+k,null,id==='D1'?0:lo+k])})};
    }});
  vm.runInContext(fs.readFileSync('src/dranalyser/application/static/inspection-workbench.js','utf8'),context);
  context.renderInspectionWorkbench(host,record,{incident_id:'public',number:1},controller);
  return {calls,nodes,node,controller,host,setReply(fn){pointReply=fn},render(){context.renderInspectionWorkbench(host,record,{incident_id:'public',number:1},controller);}};
}
const settle=async()=>{for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));};
(async()=>{
 const local=fixture(100);await settle();
 assert.equal(local.calls.length,2);assert.ok(local.calls.every(url=>url.includes('/samples?')));
 local.node('.inspection-plots').onkeydown({key:'ArrowRight',preventDefault(){}});await settle();
 assert.equal(local.calls.length,2,'keyboard cursors must reuse exact native intervals');
 assert.match(local.node('.inspection-values tbody').innerHTML,/>1<small>/);
 local.node('[data-action=add-pin]').onclick();await settle();
 local.node('pin:C').value='7';local.node('pin:C').onchange();await settle();
 assert.match(local.node('.inspection-live-cursor').textContent,/Cursor C/);
 local.node('remove:C').onclick();await settle();
 assert.match(local.node('.inspection-live-cursor').textContent,/Cursor A/);
 assert.ok(!local.node('.inspection-live-cursor').textContent.includes('undefined'));
 local.controller.abort();
 const many=fixture(25001,[...Array.from({length:9},(_,i)=>({id:'A'+(i+1),label:'Analog',kind:'analog',units:'V',trace:[]})),
  ...Array.from({length:12},(_,i)=>({id:'D'+(i+1),label:'Digital',kind:'digital',units:'state',trace:[],activity:{transition_count:i<9?2:0}}))]);await settle();
 assert.equal(many.calls.length,3,'all analogs and a separate digital page require bounded cursor batches');
 for(const url of many.calls)assert.ok(JSON.parse(new URL('http://localhost'+url).searchParams.get('channel_ids')).length<=8);
 assert.match(many.node('.inspection-values tbody').innerHTML,/A9/);
 assert.match(many.node('.inspection-page').textContent,/1–8 of 9/);
 many.controller.abort();
 const overview=fixture(25001);await settle();
 assert.equal(overview.calls.length,1);assert.ok(overview.calls[0].includes('/points?'));
 assert.deepEqual(JSON.parse(new URL('http://localhost'+overview.calls[0]).searchParams.get('indices')),[0,25000]);
 let resolveOld;
 overview.setReply(()=>new Promise(resolve=>resolveOld=resolve));
 overview.node('.inspection-plots').onkeydown({key:'ArrowRight',preventDefault(){}});await settle();
 const status=overview.node('.inspection-load').textContent;
 overview.controller.abort();overview.host.isConnected=false;
 resolveOld({ok:false,json:async()=>({detail:'obsolete recording error'})});await settle();
 assert.equal(overview.node('.inspection-load').textContent,status,'aborted recording errors must not overwrite status');
 console.log('Workbench transport: local exact cursor reuse, one overview batch and aborted-error isolation passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
