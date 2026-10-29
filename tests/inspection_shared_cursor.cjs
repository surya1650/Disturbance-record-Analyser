'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const model=require('../src/dranalyser/application/static/inspection-model.js');
const readings=require('../src/dranalyser/application/static/inspection-readings.js');
const source=fs.readFileSync('src/dranalyser/application/static/inspection-workbench.js','utf8');
const nodes=new Map();
function node(key){if(!nodes.has(key))nodes.set(key,{innerHTML:'',textContent:'',dataset:{},focus(){},setAttribute(){}});return nodes.get(key);}
const svg={dataset:{trace:'A1'},innerHTML:'',parentElement:{querySelector:()=>node('labels')},querySelector:()=>node('layer'),getBoundingClientRect:()=>({left:0,width:1000})};
const inline=node('inline');inline.dataset.reading='A1';
const digital=node('digital');digital.dataset.reading='D1';
const mount={innerHTML:'',querySelector:node,querySelectorAll(selector){
 if(selector==='[data-trace]')return[svg];
 if(selector==='[data-reading]')return[inline,digital];
 return[];
},scrollIntoView(){}};
const host={isConnected:true,querySelector:()=>mount},controller=new AbortController(),calls=[];
const record={file:'source.cfg',revision:1,sample_count:1001,source_sha256:{'source.cfg':'sourcehash'},nominal_frequency_hz:50,time_basis:{minimum_interval_s:.001},timeline:{},inventory:[],channels:[
 {id:'A1',label:'VA',kind:'analog',units:'V (CFG-declared, unverified)',trace:[[0,0,0],[1000,1,1000]],rms_trace:[[0,0,null],[20,.02,12],[1000,1,12]]},
 {id:'D1',label:'Trip',kind:'digital',units:'state',trace:[],activity:{transition_count:1}}
]};
function measurement(index,hash='sourcehash',rms=10){return{file:record.file,revision:1,source_sha256:{'source.cfg':hash},index,window:{start_index:Math.max(0,index-19),stop_index:index+1,end_s:index/1000},channels:{A1:{id:'A1',label:'VA',units:record.channels[0].units,status:'observed',rms,fundamental_rms:rms,total_rms:12,phasor:[rms,0],dc:0,relative_residual:0}}};}
let held=null,wrong=false,wrongRms=false;
const context=vm.createContext({DRInspection:model,DRReadings:readings,escapeHtml:String,AbortController,URLSearchParams,setTimeout,clearTimeout,
 fetch:async url=>{
  calls.push(url);const q=new URL('http://localhost'+url).searchParams;
  if(url.includes('/measurements?')){const index=Number(q.get('index'));if(index===200)return new Promise(resolve=>{held=resolve});return{ok:true,json:async()=>measurement(index,wrong?'wrong':'sourcehash')};}
  if(url.includes('/samples?')){const lo=Number(q.get('start_index')),hi=Number(q.get('stop_index')),digital=q.get('channel_id')==='D1';return{ok:true,json:async()=>({file:record.file,revision:1,source_sha256:record.source_sha256,channel_id:q.get('channel_id'),samples:Array.from({length:hi-lo},(_,k)=>[lo+k,(lo+k)/1000,digital?(lo+k)%2:lo+k]),...(q.get('include_rms')==='true'?{rms_samples:Array.from({length:hi-lo},(_,k)=>[lo+k,(lo+k)/1000+(wrongRms?.001:0),lo+k<20?null:20+(lo+k)%7])}:{})})};}
  if(url.includes('/points?'))return{ok:true,json:async()=>({file:record.file,revision:1,source_sha256:record.source_sha256,channels:JSON.parse(q.get('channel_ids')).map(id=>({id,samples:JSON.parse(q.get('indices')).map(index=>[index,index/1000,id==='D1'?index%2:index])}))})};
  throw Error('Unexpected cursor transport '+url);
 }});
vm.runInContext(source,context);context.renderInspectionWorkbench(host,record,{incident_id:'incident',number:1},controller);
const settle=async()=>{for(let i=0;i<12;i++)await new Promise(resolve=>setImmediate(resolve));};
(async()=>{
 await settle();assert.match(inline.innerHTML,/One-cycle RMS/);assert.match(inline.innerHTML,/Fundamental RMS/);assert.match(inline.innerHTML,/>12\.0000 /);assert.match(inline.innerHTML,/>10\.0000 /);
 svg.onclick({clientX:100});await settle();assert.match(node('.inspection-live-cursor').textContent,/Cursor A · sample 100/);assert.match(inline.innerHTML,/>100\.000 /);assert.match(digital.innerHTML,/State: 0/);
 const lockedCalls=calls.length,lockedValues=inline.innerHTML,lockedVectors=node('.inspection-vector-charts').innerHTML;
 svg.onpointermove({clientX:601});await new Promise(resolve=>setTimeout(resolve,100));await settle();
 assert.equal(calls.length,lockedCalls,'moving hover while pinned must not request or replace observations');assert.equal(inline.innerHTML,lockedValues);assert.equal(node('.inspection-vector-charts').innerHTML,lockedVectors);assert.match(node('.inspection-live-cursor').textContent,/sample 100/);
 node('.inspection-follow-hover').onclick();await settle();assert.match(node('.inspection-live-cursor').textContent,/Hover · sample 601/);assert.match(digital.innerHTML,/State: 1/);
 svg.onclick({clientX:200});await settle();assert.ok(held,'held request reached Fourier endpoint');svg.onclick({clientX:300});await settle();assert.match(node('.inspection-live-cursor').textContent,/sample 300/);
 const newest=inline.innerHTML;held({ok:true,json:async()=>measurement(200,'sourcehash',333)});await settle();assert.equal(inline.innerHTML,newest,'late Fourier response cannot replace a newer cursor');
 const beforeRms=calls.length;node('.inspection-mode').onchange({target:{value:'rms'}});await settle();
 const rmsRequests=calls.slice(beforeRms).filter(url=>url.includes('/samples?'));assert.equal(rmsRequests.length,2);assert.equal(rmsRequests.filter(url=>new URL('http://localhost'+url).searchParams.get('include_rms')==='true').length,1,'only analog intervals request RMS samples');
 assert.ok((svg.innerHTML.match(/L/g)||[]).length>950,'RMS mode uses exact native samples rather than the two-point envelope');
 svg.onwheel({clientX:500,deltaY:-1,preventDefault(){}});await settle();
 assert.ok((svg.innerHTML.match(/L/g)||[]).length>600,'zoomed RMS still renders every returned supported observation');
 const lastAnalog=calls.filter(url=>url.includes('/samples?')&&new URL('http://localhost'+url).searchParams.get('channel_id')==='A1').at(-1),zoomQuery=new URL('http://localhost'+lastAnalog).searchParams;
 assert.equal(zoomQuery.get('include_rms'),'true');assert.ok(Number(zoomQuery.get('stop_index'))-Number(zoomQuery.get('start_index'))<1001,'zoom sends the bounded viewport only');
 wrongRms=true;node('.inspection-mode').onchange({target:{value:'rms'}});await settle();assert.match(node('.inspection-load').textContent,/One-cycle RMS response identity changed/);wrongRms=false;
 wrong=true;svg.onclick({clientX:400});await settle();assert.match(node('.inspection-load').textContent,/source identity changed/);assert.ok(!inline.innerHTML.includes('>10.0000 '),'wrong-source phasor must not leak into display');
 controller.abort();
 const a=measurement(100);a.channels.A2={...a.channels.A1,id:'A2',units:'A',phasor:[0,-5],fundamental_rms:5,total_rms:6};
 let view=readings.cursorView(a,'A1');assert.equal(view.channels.get('A2').angle_deg,-90);assert.equal(view.groups.voltage.length,1);assert.equal(view.groups.current.length,1);assert.equal(view.channels.get('A2').sample_rms,6);
 a.channels.A1={...a.channels.A1,phasor:[0,0],fundamental_rms:0};view=readings.cursorView(a,'A1');assert.equal(view.channels.get('A1').rms,0);assert.equal(view.channels.get('A2').angle_deg,null,'zero explicit reference cannot manufacture angles');
 assert.ok(!readings.vectorMarkup(view).includes('NaN'));
 const raw=measurement(100);raw.channels.A1.units='raw counts';view=readings.cursorView(raw);
 assert.equal(view.groups.voltage.length,0);assert.equal(view.groups.current.length,0);
 assert.match(readings.vectorMarkup(view),/review CT\/VT scaling \(raw counts\)/,'unscaled vector refusal must name the required input');
 console.log('Shared cursor: pin/follow, exact digital states, one-cycle values, stale/hash rejection, relative phase and zero references passed');
})().catch(error=>{controller.abort();console.error(error);process.exitCode=1;});
