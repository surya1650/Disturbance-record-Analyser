'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const model=require('../src/dranalyser/application/static/inspection-model.js');
function fixture(n){
  const nodes=new Map();
  function node(key){if(!nodes.has(key))nodes.set(key,{innerHTML:'',textContent:'',dataset:{},focus(){}});return nodes.get(key);}
  const mount={querySelector:node,querySelectorAll(){return []},scrollIntoView(){}};
  const host={isConnected:true,querySelector(){return mount}};
  const record={file:'x.cfg',revision:1,sample_count:n,source_sha256:{'x.cfg':'aaa'},inventory:[],time_basis:{},
    channels:[{id:'A1',label:'A',kind:'analog',units:'raw counts',trace:[]},{id:'D1',label:'D',kind:'digital',units:'state',trace:[]}]};
  const calls=[],controller=new AbortController();
  let pointReply=null;
  const context=vm.createContext({DRInspection:model,DRReadings:require('../src/dranalyser/application/static/inspection-readings.js'),escapeHtml:String,AbortController,URLSearchParams,setTimeout,clearTimeout,
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
 local.controller.abort();
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
