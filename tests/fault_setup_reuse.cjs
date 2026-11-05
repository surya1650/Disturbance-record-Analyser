'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context=vm.createContext({setTimeout});vm.runInContext(fs.readFileSync('src/dranalyser/application/static/fault-calculation.js','utf8')+';globalThis.calc=DRFaultCalculation',context);const calc=context.calc;
const id='INCIDENT-'+'a'.repeat(32),review={confirmed_line:true,confirmed_same_event:true,ends:{S:{record:'near.cfg',name:'Synthetic near',current_direction:'bus-to-line'},R:{record:'far.cfg',name:'Synthetic far',current_direction:'bus-to-line'}}};
const row={incident_id:'synthetic-reuse',number:3,state:'needs_review',files:[{name:'near.cfg',sha256:'a'},{name:'far.cfg',sha256:'b'}],bundle:{files:[{kind:'comtrade',name:'near.cfg',ok:true},{kind:'comtrade',name:'far.cfg',ok:true}]},metadata:{line_id:id,incident_line:{line_id:id,review},assignments:{'near.cfg':{end:'S',role:'primary',instrument_review:{record_hash:'a',ratios:{A1:{primary:1000,secondary:1}}}},'far.cfg':{end:'R',role:'primary'}}}};
const html=calc.panel(row,{lines:[{id:'other',name:'Another engineering line'}]});
assert.ok(!html.includes('name="line_id"')&&!html.includes('name="S"')&&!html.includes('name="R"'),'saved Setup is the one input source even with other registry entries');
assert.ok(!html.includes('data-engineering-model-selection'));assert.match(html,/name="confirmed" checked/);assert.match(html,/#setup\/synthetic-reuse/);
const old=JSON.stringify(row),single=JSON.parse(old);delete single.metadata.incident_line.review.ends.R;single.metadata.incident_line.review.confirmed_same_event=false;
assert.equal(calc.savedChoices(single).confirmed,true,'one end needs no opposite-end event confirmation');assert.equal(JSON.stringify(row),old);
function fixture(){
 const handlers={},confirmed={name:'confirmed',checked:true,disabled:false},button={disabled:false},status={textContent:'',innerHTML:''},controls=[confirmed,button];
 const form={dataset:{},elements:{namedItem:key=>{assert.equal(key,'confirmed','local calculation cannot read a second editable model/end field');return confirmed;}},addEventListener:(name,fn)=>{handlers[name]=fn;},querySelectorAll:()=>controls};
 const root={isConnected:true,querySelector:key=>key==='[data-fault-form]'?form:key==='[data-fault-status]'?status:null};
 return {host:{querySelector:()=>root},root,status,controls,submit:()=>handlers.submit({preventDefault(){}})};
}
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));};
(async()=>{
 const good=fixture(),calls=[];
 calc.bind(row,good.host,undefined,{request:async(path,options)=>{calls.push([path,options]);if(!options.method)return {revision:3,line_id:id,missing:[]};return {};}});
 await settle();assert.match(good.status.textContent,/Saved Setup facts are complete/);await good.submit();
 assert.equal(calls.length,2);assert.match(calls[0][0],/line-inputs\?revision=3$/);assert.match(calls[1][0],/\/review$/);
 const body=JSON.parse(calls[1][1].body);assert.equal(body.line_id,id);assert.equal(body.revision,3);assert.equal(body.assignments['near.cfg'].end,'S');assert.equal(body.assignments['far.cfg'].end,'R');assert.equal(body.assignments['near.cfg'].instrument_review.ratios.A1.primary,1000);assert.equal(JSON.stringify(row),old);
 const missing=fixture();let writes=0;
 calc.bind(row,missing.host,undefined,{request:async(path,options)=>{if(options.method){writes++;return {};}return {revision:3,line_id:id,missing:['Confirm S current sign <img src=x>']};}});
 await settle();assert.match(missing.status.innerHTML,/Still needed in Setup/);assert.match(missing.status.innerHTML,/Complete these saved line facts/);assert.ok(!missing.status.innerHTML.includes('<img'));await missing.submit();assert.equal(writes,0);assert.ok(missing.controls.every(control=>!control.disabled));
 for(const reply of [{revision:2,line_id:id,missing:[]},{revision:3,line_id:'other',missing:[]}]){
  const stale=fixture();writes=0;calc.bind(row,stale.host,undefined,{request:async(path,options)=>{if(options.method)writes++;return reply;}});await settle();await stale.submit();assert.equal(writes,0);assert.match(stale.status.textContent,/another revision/);
 }
 const gone=fixture();let release;
 calc.bind(row,gone.host,undefined,{request:async(path,options)=>{if(options.method)throw new Error('A detached page cannot write');return await new Promise(resolve=>{release=resolve;});}});await settle();gone.root.isConnected=false;release({revision:3,line_id:id,missing:[]});await settle();assert.equal(gone.status.textContent,'');
 console.log('Fault Setup reuse: canonical line/ends/confirmations, authoritative missing facts, no stale writes and exact source-bound inputs passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
