'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const study=require('../src/dranalyser/application/static/event-study.js');
const id='a'.repeat(32),lineId='INCIDENT-'+id;
const files=['S.cfg','S.dat','R.cfg','R.dat'].map((name,i)=>({name,sha256:String(i+1).repeat(64)}));
const inventory=['S','R'].map(end=>({name:end+'.cfg',kind:'comtrade',content_hash:end.toLowerCase().repeat(64)}));
const records=inventory.map((item,i)=>({file:item.name,source_sha256:{[item.name]:files[i*2].sha256},sample_count:200}));
const review={confirmed_same_event:true,ends:{S:{record:'S.cfg',name:'Reviewed reference'},R:{record:'R.cfg',name:'Reviewed other'}}};
const row={incident_id:id,number:7,bundle:{files:inventory},files,metadata:{line_id:lineId,
  incident_line:{version:1,line_id:lineId,source_sha256:Object.fromEntries(files.map(file=>[file.name,file.sha256])),review},
  assignments:{'S.cfg':{end:'S',role:'primary'},'R.cfg':{end:'R',role:'primary'}}}};
const original=JSON.stringify(row),defaults=study.setupDefaults(row,records);
assert.equal(defaults.ends.S.record,'S.cfg');assert.equal(defaults.ends.R.record,'R.cfg');
assert.equal(defaults.ends.S.substation,'Reviewed reference');assert.equal(defaults.same_event_confirmed,true);
assert.equal(defaults.ends.S.timing_mode,'auto');assert.equal(defaults.ends.S.relay_distance,null);
assert.equal(JSON.stringify(row),original,'Setup reuse never mutates the immutable revision');
for(const mutate of [
  value=>{value.metadata.line_id='another';},
  value=>{value.metadata.incident_line.line_id='INCIDENT-'+'b'.repeat(32);},
  value=>{value.files[0].sha256='b'.repeat(64);},
  value=>{delete value.metadata.incident_line.source_sha256['S.dat'];},
  value=>{value.metadata.assignments['S.cfg'].end='R';},
  value=>{value.metadata.assignments['R.cfg'].role='excluded';},
  value=>{value.metadata.assignments['unselected.cfg']={role:'primary',end:'S'};},
  value=>{value.metadata.incident_line.review.ends.R.record='S.cfg';},
  value=>{delete value.metadata.incident_line.review.ends.S;},
  value=>{value.bundle.files[0].duplicate_of='original.cfg';},
]){
  const invalid=structuredClone(row);mutate(invalid);
  assert.equal(study.setupDefaults(invalid,records),null,'stale/ambiguous physical facts cannot silently populate choices');
}
assert.equal(study.setupDefaults(row,records.slice(1)),null);
const unconfirmed=structuredClone(row);unconfirmed.metadata.incident_line.review.confirmed_same_event=false;
assert.equal(study.setupDefaults(unconfirmed,records).same_event_confirmed,false);
const single=structuredClone(row);delete single.metadata.incident_line.review.ends.R;delete single.metadata.assignments['R.cfg'];
assert.equal(study.setupDefaults(single,records).same_event_confirmed,false);
assert.equal(study.setupDefaults({...row,metadata:{}},records),null,'older incidents retain explicit selection');
const remoteOnly=structuredClone(row);delete remoteOnly.metadata.incident_line.review.ends.S;delete remoteOnly.metadata.assignments['S.cfg'];
const remoteDefaults=study.setupDefaults(remoteOnly,records);
assert.deepEqual(Object.keys(remoteDefaults.ends),['R']);assert.equal(remoteDefaults.ends.R.record,'R.cfg');
assert.equal(remoteDefaults.same_event_confirmed,false,'a single R source cannot inherit a stale opposite-end confirmation');

// A complete zero is data; malformed or unfinished optional readings are named and omitted.
assert.deepEqual(study.relayReading({},'S'),{reading:null,issues:[]});
const zero={'S.relay.km':'0','S.relay.reference':'R','S.relay.evidence':'Synthetic relay sheet'};
assert.deepEqual(study.relayReading(zero,'S'),{reading:{km:0,reference:'R',evidence:'Synthetic relay sheet'},issues:[]});
for(const km of ['-1','NaN','Infinity','1000001']){
  const checked=study.relayReading({...zero,'S.relay.km':km},'S');
  assert.equal(checked.reading,null);assert.match(checked.issues.join(' '),/finite number from 0/);
}
const missingSource=study.relayReading({...zero,'S.relay.evidence':''},'S');
assert.equal(missingSource.reading,null);assert.equal(missingSource.issues.length,1);
assert.match(missingSource.issues[0],/source of this reading/);
assert.equal(study.relayReading({...zero,'S.relay.evidence':'x'.repeat(1001)},'S').reading,null);
assert.equal(study.collect({'S.record':'S.cfg','S.timing_mode':'auto',...zero}).ends.S.relay_distance.km,0);

class Field{
  constructor(name){this.name=name;this.value='';this.checked=false;this.disabled=false;this.validated=0;}
  reportValidity(){this.validated++;return !this.name.includes('.relay.');}
  removeAttribute(){}
}
const fields={same_event_confirmed:new Field('same_event_confirmed')};
for(const role of ['S','R'])for(const key of ['record','substation','timing_mode','pre.0','pre.1','fault.0','fault.1','post.0','post.1','relay.km','relay.reference','relay.evidence'])fields[role+'.'+key]=new Field(role+'.'+key);
const status={textContent:'',classList:{toggle(){}}},submit={disabled:true};
const handlers={},views=new Map(),node=key=>{
  if(!views.has(key))views.set(key,{hidden:false,textContent:'',innerHTML:'',classList:{toggle(){}}});
  return views.get(key);
};
const form={elements:{namedItem:name=>fields[name]},querySelector:selector=>selector==='[type=submit]'?submit:node(selector),
  querySelectorAll:selector=>selector==='input,select'?[...Object.values(fields)]:[...Object.values(fields),submit],
  addEventListener:(name,handler)=>{handlers[name]=handler;}};
const output={innerHTML:'',querySelector:()=>null,addEventListener(){}};
const root={isConnected:true,matches:()=>true,querySelector:selector=>selector==='form'?form:selector==='[data-event-study-status]'?status:output,dispatchEvent(){}};
const requests=[],saved=[];
let storedInputs={same_event_confirmed:false,ends:{}},storedVersion=0,getRevision=7,getRecords=records,holdGet=null;
const api=async(path,options={})=>{
  requests.push({path,options});
  const body=options.body?JSON.parse(options.body):{};
  if(path.includes('/regions'))return {file:body.record,revision:7,source_sha256:records.find(item=>item.file===body.record).source_sha256,
    sample_count:200,status:'selected',pre:[0,30],fault:[50,110],post:[130,190]};
  if(options.method==='PUT'){
    saved.push(body.inputs);storedInputs=body.inputs;storedVersion++;
    return {version:storedVersion,inputs:body.inputs};
  }
  if(path.endsWith('/report'))return {incident_id:id,revision:7,ends:body.inputs.ends,distance:{},notes:[]};
  const response={revision:getRevision,version:storedVersion,records:getRecords,inputs:storedInputs};
  if(holdGet)return new Promise(resolve=>{holdGet.resolve=()=>resolve(response);});
  return response;
};
const context=vm.createContext({api,AbortController,console,setTimeout,clearTimeout});
vm.runInContext(fs.readFileSync('src/dranalyser/application/static/event-study.js','utf8')+';globalThis.view=DREventStudy',context);
const settle=async()=>{for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));};
(async()=>{
  const view=context.view.bind(row,root,new AbortController().signal);
  await settle();
  assert.equal(fields['S.record'].value,'S.cfg');assert.equal(fields['R.record'].value,'R.cfg');
  assert.equal(fields['S.substation'].value,'Reviewed reference');assert.equal(fields.same_event_confirmed.checked,true);
  assert.equal(requests.filter(value=>value.path.endsWith('/regions')).length,2,'timings use existing automatic source selection');
  assert.match(status.textContent,/saved Setup/);
  fields['S.relay.km'].value='7.250';fields['S.relay.reference'].value='S';fields['S.relay.evidence'].value='';
  handlers.input({target:fields['S.relay.km']});
  assert.match(node('[data-relay-input-status="S"]').textContent,/source of this reading/);
  await handlers.submit({preventDefault(){}});
  assert.equal(saved.length,1);assert.equal(saved[0].ends.S.relay_distance,null,'incomplete optional reading never reaches strict backend');
  assert.equal(fields['S.relay.km'].value,'7.250','build retains exact entered draft text');
  assert.equal(fields['S.relay.reference'].value,'S');assert.equal(fields['S.relay.evidence'].value,'');
  assert.match(status.textContent,/Event report ready.*source of this reading.*excluded/);
  assert.match(output.innerHTML,/Optional relay readings excluded/);
  assert.equal(fields['S.relay.km'].validated,0,'native optional validity never blocks observation report');
  assert.ok(fields['S.pre.0'].validated>0,'ordinary interval validity remains enforced');
  fields['S.relay.km'].value='0';fields['S.relay.evidence'].value='Synthetic relay event';
  await handlers.submit({preventDefault(){}});
  assert.equal(saved[1].ends.S.relay_distance.km,0);assert.equal(saved[1].ends.S.relay_distance.evidence,'Synthetic relay event');
  assert.doesNotMatch(output.innerHTML,/Optional relay readings excluded/);
  fields['S.relay.km'].value='invalid entered draft';fields['S.relay.evidence'].value='';
  await handlers.submit({preventDefault(){}});
  assert.equal(fields['S.relay.km'].value,'invalid entered draft');assert.equal(saved[2].ends.S.relay_distance,null);
  assert.match(status.textContent,/finite number from 0/);
  // Source changes never attach the prior source's reading to another recording.
  fields['S.record'].value='R.cfg';handlers.change({target:fields['S.record']});
  assert.equal(fields['S.relay.km'].value,'');assert.equal(fields.same_event_confirmed.checked,false);
  fields['S.record'].value='S.cfg';handlers.change({target:fields['S.record']});
  assert.equal(fields['S.relay.km'].value,'invalid entered draft','returning to a source restores only its own draft');
  await settle();
  // An existing explicit event-study selection takes precedence over Setup defaults.
  storedInputs={same_event_confirmed:false,ends:{S:{record:'R.cfg',substation:'Explicit display label',timing_mode:'manual',pre:[0,10],fault:[20,50],post:null,relay_distance:null}}};storedVersion=4;
  view.destroy();context.view.bind(row,root,new AbortController().signal);await settle();
  assert.equal(fields['S.record'].value,'R.cfg');assert.equal(fields['S.substation'].value,'Explicit display label');
  assert.equal(fields['S.timing_mode'].value,'manual');assert.equal(fields.same_event_confirmed.checked,false);
  assert.equal(fields['R.record'].value,'');
  // A saved R-only report reloads without moving the physical R capture into S.
  storedInputs={same_event_confirmed:false,ends:{R:{record:'R.cfg',substation:'Remote only',timing_mode:'auto',pre:null,fault:null,post:null,relay_distance:null}}};storedVersion=5;
  const reportsBefore=requests.filter(value=>value.path.endsWith('/report')).length;
  context.view.bind(remoteOnly,root,new AbortController().signal);await settle();
  assert.equal(fields['S.record'].value,'');assert.equal(fields['R.record'].value,'R.cfg');
  assert.equal(fields.same_event_confirmed.checked,false);assert.match(status.textContent,/Saved event report loaded/);
  assert.equal(requests.filter(value=>value.path.endsWith('/report')).length,reportsBefore+1);
  const remoteRequest=JSON.parse(requests.filter(value=>value.path.endsWith('/report')).at(-1).options.body);
  assert.deepEqual(Object.keys(remoteRequest.inputs.ends),['R']);
  const beforeChoices=fields['S.record'].innerHTML;getRevision=8;getRecords=[{file:'stale.cfg'}];
  context.view.bind(row,root,new AbortController().signal);await settle();
  assert.match(status.textContent,/another revision/);assert.equal(fields['S.record'].innerHTML,beforeChoices,'stale response cannot replace recording choices');
  getRevision=7;getRecords=records;holdGet={};
  const delayed=context.view.bind(row,root,new AbortController().signal);
  await settle();delayed.destroy();const beforeLate=status.textContent;holdGet.resolve();await settle();
  assert.equal(status.textContent,beforeLate,'cancelled response cannot replace the current status');
  assert.equal(fields['S.record'].innerHTML,beforeChoices);
  assert.equal(JSON.stringify(row),original);
  console.log('Event Setup reuse, source/revision gates, optional relay drafts and exact provenance checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
