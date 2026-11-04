'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function node(){return {innerHTML:'',textContent:'',value:'',dataset:{},hidden:false,isConnected:true,handlers:{},classList:{toggle(name,value){this[name]=value;},add(){},remove(){}},addEventListener(type,fn){this.handlers[type]=fn;},append(){},querySelector(){return node();}};}
const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);};
const links=['upload','analyse','compare','report'].map(task=>({...node(),dataset:{nav:task}}));
const views=['overview','upload','setup','detail','integrations','catalogue'].map(id=>({...node(),id}));
const location={hash:'#overview'},row={incident_id:'sample',name:'Synthetic event',number:2,state:'needs_review',source:'manual',created:1,files:[],bundle:{files:[]},metadata:{}};
const document={hidden:false,getElementById:get,querySelectorAll:selector=>selector==='[data-nav]'?links:selector==='.view'?views:[],querySelector:()=>null};
const requests=[],uploads=[],mounts=[];let captured=0,pendingReady=null;
const context=vm.createContext({document,location,inspectionController:null,history:{},window:{addEventListener(){}},Date,AbortController,URLSearchParams,Option:function(){},setInterval(){},setTimeout,clearTimeout,
 FormData:function(){this.fields=[];this.append=(...values)=>this.fields.push(values);},
 XMLHttpRequest:function(){uploads.push(this);this.upload={};this.open=()=>{};this.setRequestHeader=()=>{};this.send=data=>{this.data=data;};},
 DRRecordingSetup:{ready:async(request,id,options)=>pendingReady?new Promise(resolve=>{pendingReady={resolve,options};}):row,mount:async(host,current,options)=>{mounts.push({host,row:current,options});host.innerHTML='Recording setup';return {capture(){captured++;}};}},
 fetch:async(path)=>{requests.push(path);return {ok:true,json:async()=>path==='/api/config'?{token:'test',lines:[],mapping_targets:{}}:path.startsWith('/api/incidents?')?{items:[{id:'sample',name:'Synthetic event',number:2,state:'needs_review',updated:1}],summary:{needs_review:1}}:row};}});
vm.runInContext(fs.readFileSync('src/dranalyser/application/static/app.js','utf8'),context);
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));};
const file=name=>({name,size:20});
(async()=>{
 await settle();location.hash='#setup/sample';await context.route();
 assert.equal(mounts.length,1);assert.equal(views.find(view=>view.id==='setup').hidden,false);assert.equal(links[0].classList.active,true);
 assert.equal(links[1].href,'#incident/sample/2/waveforms');assert.equal(mounts[0].options.isCurrent(),true);
 const first=mounts[0];location.hash='#overview';await context.route();
 assert.equal(first.options.signal.aborted,true);assert.equal(first.options.isCurrent(),false);assert.equal(captured,1);
 pendingReady=true;location.hash='#setup/sample';const old=context.route();await settle();
 const waiting=pendingReady;location.hash='#overview';await context.route();waiting.resolve(row);await old;
 assert.equal(mounts.length,1,'a late parse response cannot mount setup after navigation');pendingReady=null;
 location.hash='#upload';await context.route();context.chooseFiles([file('Original.cfg')]);context.submitUpload({preventDefault(){}});
 const upload=uploads.at(-1);assert.equal(upload.data.fields[0][1].name,'Original.cfg');
 upload.status=202;upload.responseText=JSON.stringify({incident_id:'sample',revision:2});upload.onload();
 assert.equal(location.hash,'setup/sample','upload completion opens setup before analysis');
 location.hash='#upload';await context.route();context.chooseFiles([file('Another.cfg')]);context.submitUpload({preventDefault(){}});
 const lateUpload=uploads.at(-1);context.chooseFiles([file('New.cfg')]);location.hash='#overview';await context.route();
 lateUpload.status=202;lateUpload.responseText=JSON.stringify({incident_id:'sample',revision:3});lateUpload.onload();
 assert.equal(location.hash,'#overview','a delayed upload never hijacks a newer route');
 assert.ok(get('selected-files').innerHTML.includes('New.cfg'),'newly selected files are retained after the earlier submission completes');
 assert.ok(!get('selected-files').innerHTML.includes('Another.cfg'));
 assert.match(get('notice').textContent,/Upload completed/);
 console.log('Recording setup routes: upload-first setup, existing incident links, abort/stale guards and late-upload retention passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
