'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const inputs=require('../src/dranalyser/application/static/inspection-inputs.js');
// Exercise the real source-analysis binding: a line declaration must never opt
// the user into an unrelated missing-CT assumption.
const nodes=new Map();
const node=key=>{if(!nodes.has(key))nodes.set(key,{value:'',innerHTML:'',textContent:'',hidden:false,dataset:{},insertBefore(){},querySelector:node,querySelectorAll(){return [];}});return nodes.get(key);};
const section=node('section'),host={isConnected:true,append(){},querySelector(){return null;}};
const controller=new AbortController();
const context=vm.createContext({document:{createElement(){return section;}},DRSourceInputs:inputs,
 DRSourceReport:{esc:String,schematic(){return '';}},DROperatorWorkspace:{mount(){return {update(){}};}},
 AbortController,URLSearchParams,setTimeout(){return 1;},clearTimeout(){},
 config:{mapping_targets:{analog:[],digital:[]}},
 fetch:async url=>({ok:true,json:async()=>url==='/api/source-lines'?{items:[{id:'LINE',kv:132,name:'Supplied corridor',parameter_status:'provisional',provenance:'Test declaration',sha256:'abc'}]}:{status:'pending',detail:'Waiting',file:'raw.cfg',revision:1,options:{voltage_kv:0,mappings:{}},source_sha256:{'raw.cfg':'abc'}}})
});
vm.runInContext(fs.readFileSync('src/dranalyser/application/static/inspection-analysis.js','utf8'),context);
context.mountSourceAnalysis(host,{file:'raw.cfg',channels:[],source_sha256:{'raw.cfg':'abc'}},{incident_id:'test',number:1,bundle:{files:[]}},controller,null);
(async()=>{
 for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
 node('.source-line-mode').value='LINE';node('.source-line-mode').onchange();
 assert.equal(node('.source-voltage').value,'0','line voltage cannot choose an assumed missing CT ratio');
 assert.match(node('.source-line-notes').textContent,/Test declaration/);
 node('.source-voltage').value='220';node('.source-line-mode').onchange();
 assert.equal(node('.source-voltage').value,'220','explicit legacy display assumptions remain user choices');
 controller.abort();
 console.log('Line-model changes retain unresolved CT ratios and preserve explicit display assumptions');
})().catch(error=>{console.error(error);process.exitCode=1;});
