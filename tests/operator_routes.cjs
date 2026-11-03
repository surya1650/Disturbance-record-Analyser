'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function node(){return {innerHTML:'',textContent:'',value:'',dataset:{},hidden:false,handlers:{},classList:{toggle(name,value){this[name]=value;}},addEventListener(type,fn){this.handlers[type]=fn;},append(){},querySelector(){return node();}};}
const nodes=new Map(),get=id=>{if(id==='review-form'||id==='retry-job')return null;if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);};
const links=['upload','analyse','compare','report'].map(task=>({...node(),dataset:{nav:task}}));
const views=['overview','upload','detail','integrations','catalogue'].map(id=>({...node(),id}));
let tabClicks=0;const compareTab={click(){tabClicks++;}},historyCalls=[],requests=[];
const location={hash:'#overview'},row={incident_id:'sample',name:'Incident',number:2,state:'needs_review',source:'manual',created:1,files:[],bundle:{files:[]},metadata:{},activity:[],revisions:[{number:2,state:'needs_review',created:1}]};
const document={hidden:false,getElementById:get,createElement:()=>node(),querySelectorAll:selector=>selector==='[data-nav]'?links:selector==='.view'?views:[],querySelector:selector=>selector==='[data-workspace-tab="compare"]'?compareTab:node()};
let mounted=0;
const context=vm.createContext({document,location,inspectionController:null,history:{replaceState(a,b,hash){historyCalls.push(hash);location.hash=hash;}},window:{addEventListener(){}},Date,URLSearchParams,Option:function(){},FormData:function(){},setInterval(){},setTimeout,clearTimeout,
  loadStageReviewSource:async()=>{},inspectionPanel:()=>'<section>Source view</section>',mountInspection(){mounted++;},mappingEditor:()=>'',rxReviewEditor:()=>'',stageReviewEditor:()=>'',
  fetch:async(path)=>{requests.push(path);return {ok:true,json:async()=>path==='/api/config'?{token:'test',lines:[],mapping_targets:{}}:path.startsWith('/api/incidents?')?{items:[{id:'sample',name:'Incident',number:2,state:'needs_review',updated:1}],summary:{needs_review:1}}:row};}});
vm.runInContext(fs.readFileSync('src/dranalyser/application/static/app.js','utf8'),context);
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));};
(async()=>{
 await settle();location.hash='#compare';await context.route();
 assert.match(get('incident-list').innerHTML,/#incident\/sample\/2\/compare/,'the Compare task asks the user to choose an existing incident');
 assert.equal(links[2].classList.active,true);
 location.hash='#incident/sample/2/report';await context.route();
 assert.equal(get('inspection-workspace').dataset.requestedTask,'report');assert.ok(mounted>0);
 assert.match(get('detail-content').innerHTML,/incident-history/);assert.match(get('detail-content').innerHTML,/Original file inventory/);
 assert.ok(!get('detail-content').innerHTML.includes('<iframe'),'the old dense technical report must not return as the default preview');
 assert.ok(!get('detail-content').innerHTML.includes('standards-audits'));
 context.setPortalTask('compare',row);assert.equal(historyCalls.at(-1),'#incident/sample/2/compare');
 assert.equal(links[3].href,'#incident/sample/2/report');
 const before=requests.length;let prevented=false;links[2].handlers.click({preventDefault(){prevented=true;}});
 assert.equal(prevented,true);assert.equal(tabClicks,1);assert.equal(requests.length,before,'switching a task in the same incident must retain the mounted waveform/cursor tools');
 console.log('Portal routes: incident selection, report deep links, preserved history and in-place task navigation passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
