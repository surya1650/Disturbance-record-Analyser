'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const model=require('../src/dranalyser/application/static/inspection-model.js');
const readings=require('../src/dranalyser/application/static/inspection-readings.js');
const source=fs.readFileSync('src/dranalyser/application/static/inspection-workbench.js','utf8');
const channels=[...Array.from({length:64},(_,i)=>({id:'A'+(i+1),label:'Analog '+i,kind:'analog',units:i<32?'V':'A',trace:[]})),
 ...Array.from({length:16},(_,i)=>({id:'D'+(i+1),label:'Digital '+i,kind:'digital',units:'state',trace:[],activity:{transition_count:i<12?2:0,active_duration_s:.01,unknown_samples:0,high_intervals:[]}}))];
const record={file:'large.cfg',revision:1,sample_count:25001,channels,inventory:[],time_basis:{},source_sha256:{'large.cfg':'aaa'},timeline:{trigger_offset_s:.5,start_local:'2026-01-01T00:00:00.000000',ticks:[[0,0],[25000,25]]}};
const state=model.create(record);assert.equal(state.order.filter(id=>state.visible(id)).length,76);state.toggle('A1');assert.equal(state.visible('A1'),true);state.toggle('D16');assert.equal(state.visible('D16'),true);
assert.deepEqual(state.order.slice(-16,-4),Array.from({length:12},(_,i)=>'D'+(i+1)));
assert.deepEqual(model.segments([[0,0,1],[20,.02,2],[40,.04,3]],Infinity,[30]),[[[0,0,1],[20,.02,2]],[[40,.04,3]]]);
assert.equal(model.milliseconds(.5,record.timeline),'0.000 ms');assert.equal(model.milliseconds(.4,record.timeline),'-100.000 ms');
assert.match(model.relayTime(.5,record.timeline),/00:00:00.500000 relay local/);
function fixture(options={}){
 const nodes=new Map(),node=key=>{if(!nodes.has(key))nodes.set(key,{innerHTML:'',textContent:'',dataset:{},focus(){}});return nodes.get(key);};
 const mount={innerHTML:'',querySelector:node,querySelectorAll(){return [];},scrollIntoView(){}};
 const controller=new AbortController(),host={isConnected:true,querySelector(){return mount;}};
 const calls=[],pending=[];let active=0,peak=0,bad=false;
 const context=vm.createContext({DRInspection:model,DRReadings:readings,escapeHtml:String,AbortController,URLSearchParams,setTimeout,clearTimeout,
 fetch:async(url,{signal})=>{
   calls.push(url);active++;peak=Math.max(peak,active);await new Promise(resolve=>setImmediate(resolve));
   if(options.hold&&calls.length>10)await new Promise(resolve=>pending.push(resolve));
   active--;const query=new URL('http://localhost'+url).searchParams;
   assert.ok(!url.includes('/samples?'),'large all-channel view must retain bounded envelopes');
   const ids=JSON.parse(query.get('channel_ids')),indices=JSON.parse(query.get('indices'));assert.ok(ids.length<=8);
   const mismatched=options.badHash&&ids.includes('A33');if(mismatched)bad=true;
   return {ok:true,json:async()=>({file:record.file,revision:1,source_sha256:{'large.cfg':mismatched?'changed':'aaa'},channels:ids.map(id=>({id,samples:indices.map(i=>[i,i/1000,777])}))})};
 }});
 vm.runInContext(source,context);context.renderInspectionWorkbench(host,record,{incident_id:'large-public',number:1},controller);
 return {node,mount,calls,controller,host,pending,get peak(){return peak;},get bad(){return bad;}};
}
const settle=async()=>{for(let i=0;i<30;i++)await new Promise(resolve=>setImmediate(resolve));};
(async()=>{
 const f=fixture();await settle();
 assert.equal(f.calls.length,10,'76 visible channel IDs require ten <=8 batches');assert.ok(f.peak<=3);assert.equal(f.peak,3);
 assert.equal((f.node('.analog-slots').innerHTML.match(/data-trace=/g)||[]).length,64);
 assert.equal((f.node('.digital-slots').innerHTML.match(/data-trace=/g)||[]).length,12);
 assert.ok(!f.mount.innerHTML.includes('Previous channels'));assert.ok(!f.mount.innerHTML.includes('Next channels'));assert.ok(!f.mount.innerHTML.includes('Next digital'));
 assert.ok(f.node('.inspection-channel-list').innerHTML.includes('data-channel="A1" checked disabled'));
 assert.equal((f.node('.inspection-values tbody').innerHTML.match(/>777<small>/g)||[]).length,228,'all76channel values atA/B/hover are merged after complete batch validation');
 f.controller.abort();
 const invalid=fixture({badHash:true});await settle();assert.equal(invalid.bad,true);
 assert.ok(invalid.node('.inspection-load').textContent.includes('identity changed'));
 assert.ok(!invalid.node('.inspection-values tbody').innerHTML.includes('>777<small>'),'one wrong source response must invalidate the entire cursor snapshot');
 invalid.controller.abort();
 const aborted=fixture({hold:true});await settle();
 aborted.node('.inspection-plots').onkeydown({key:'ArrowRight',preventDefault(){}});await settle();
 assert.ok(aborted.pending.length<=3,'only three requests may be outstanding in a generation');
 const old=aborted.node('.inspection-values tbody').innerHTML;aborted.controller.abort();aborted.host.isConnected=false;
 for(const resolve of aborted.pending)resolve();await settle();assert.equal(aborted.node('.inspection-values tbody').innerHTML,old,'aborted generation cannot replace values');
 console.log('Restored layout:64mandatory analogs,12changed digitals,exact bounded batches,source-safe snapshots and cancelled requests passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
