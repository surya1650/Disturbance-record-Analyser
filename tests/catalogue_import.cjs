'use strict';
const assert = require('node:assert/strict');
const view = require('../src/dranalyser/application/static/catalogue.js');
const delay = () => new Promise(resolve=>setImmediate(resolve));
const deferred = () => { let resolve,reject; const promise=new Promise((yes,no)=>{resolve=yes;reject=no;}); return {promise,resolve,reject}; };
const metadata = {import_id:'a'.repeat(64),catalogue_hash:'b'.repeat(64),source:{file_name:'example.xlsx'},summary:{rows:2,transmission_rows:1,transformer_rows:1,issues:{missing_identity:1}},limits:'Unreviewed source evidence.',expected_active_hash:null,active:false};
const tl = {id:'tl1',station:'Alpha',feeder:'Beta',sheet:'C TL',row:3,raw:{ct_ratio:'400/1',vt_ratio:'132000/110'},status:'Source review required',z1:{r:1,x:2},zones:[{name:'Z1',reach_raw:'3+j4',time_raw:'.1'}],issues:[],reciprocal_candidates:[]};
const ptr = {id:'ptr1',kind:'PTR',inventory_only:true,station:'Alpha',sheet:'C PTR',row:6,transformer_capacity:'100/80 MVA',vector_group:'YNyn0',ct_available_raw:'600/1',ct_adopted_raw:'400/1',impedance_percent_raw:'12.5%',winding_voltage_raw:'220/132 kV',source_values:['100/80 MVA','220/132 kV'],source_headers:['Transformer (PTR) Capacity','Voltage  (kV)'],source_locator:{file_name:'example.xlsx',sheet:'C PTR',row:6,cells:['A6','B6']},cells:{station:"'C PTR'!A6",capacity:"'C PTR'!B6"},raw:{},issues:[]};
const catalogue = {available:true,catalogue_hash:'old-hash',source:{file_name:'old.xlsx'},summary:{rows:2,transmission_rows:1,transformer_rows:1},limits:'Unreviewed',total:2,items:[tl,ptr],facets:{circles:['C'],stations:['Alpha'],kinds:['TL','PTR']}};
assert.equal(view.validateFile({name:'good.XLSX',size:1}),'');
assert.equal(view.validateFile({name:'good.xlsx',size:view.MAX_BYTES}),'');
assert.match(view.validateFile({name:'good.xlsx',size:view.MAX_BYTES+1}),/16 MiB/);
assert.match(view.validateFile({name:'wrong.xls',size:10}),/\.xlsx/);
assert.match(view.validateFile({name:'empty.xlsx',size:0}),/empty/);
const query = new URLSearchParams(view.filters({q:'bus A & B',circle:'A/B',station:'<Station>',kind:'PTR',errors_only:true},200));
assert.equal(query.get('q'),'bus A & B');assert.equal(query.get('circle'),'A/B');assert.equal(query.get('station'),'<Station>');assert.equal(query.get('kind'),'PTR');assert.equal(query.get('offset'),'200');assert.equal(query.get('limit'),'50');assert.equal(query.get('errors_only'),'true');
const large = Array.from({length:1500},(_,i)=>`Station ${i}`);
assert.equal((view.options(large,'Station 1499','All stations').match(/<option/g)||[]).length,1501);
assert.match(view.options(large,'Station 1499','All stations'),/value="Station 1499" selected/);
const tlHTML=view.rowMarkup(tl),ptrHTML=view.rowMarkup(ptr);
assert.match(tlHTML,/Reciprocal-end candidates/);assert.match(tlHTML,/source base unconfirmed/);assert.match(tlHTML,/These values are not zone polygons/);
assert.match(ptrHTML,/PTR inventory only/);for(const value of ['100/80 MVA','YNyn0','600/1','400/1','12.5%','220/132 kV','A6','B6'])assert.ok(ptrHTML.includes(value),value);
assert.ok(!ptrHTML.includes('Unknown feeder')&&!view.tableMarkup([ptr]).includes('Relay unspecified'));
assert.ok(!ptrHTML.includes('Reciprocal-end')&&!ptrHTML.includes('Source reach / time')&&!ptrHTML.includes('registry'));
assert.ok(!ptrHTML.includes('href=')&&!ptrHTML.includes('docs.google'));
assert.match(view.rowMarkup({...tl,url:'https://docs.google.com/spreadsheets/d/sheet/edit#gid=2'}),/Open exact source row/);
assert.ok(!view.rowMarkup({...tl,url:'javascript:alert(1)'}).includes('href='));
assert.match(view.previewMarkup(metadata),/example.xlsx/);assert.match(view.previewMarkup(metadata),/1 TL rows · 1 PTR rows/);assert.match(view.previewMarkup(metadata),/Use in catalogue/);
assert.match(view.summaryMarkup({available:false}),/Upload a workbook above/);
const hostile='<img src=x onerror=alert(1)>"&';
for(const html of [view.rowMarkup({...ptr,station:hostile,source_values:{[hostile]:hostile},cells:{[hostile]:hostile}}),view.tableMarkup([{...tl,id:hostile,station:hostile,issue_count:hostile,row:hostile}]),view.previewMarkup({...metadata,source:{file_name:hostile},import_id:hostile,summary:{issues:{[hostile]:hostile}}}),view.historyMarkup([{...metadata,source:{file_name:hostile},created_at:hostile}]),view.options([hostile],hostile,'All')]) {
  assert.ok(!html.includes('<img'),html);assert.ok(html.includes('&lt;img'),html);
}

// The small DOM below exercises async workflow, pending actions, routing and stale responses.
class Element {
  constructor(host,id=''){this.host=host;this.id=id;this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.dataset={};this.textContent='';this.files=[];this._html='';this.queryCache=new Map();}
  set innerHTML(value){this._html=value;this.queryCache.clear();for(const match of value.matchAll(/\bid="([^"]+)"/g))this.host.elements.set(match[1],new Element(this.host,match[1]));}
  get innerHTML(){return this._html;}
  querySelector(selector){return this.host.elements.get(selector.slice(1))||null;}
  querySelectorAll(selector){if(this.queryCache.has(selector))return this.queryCache.get(selector);const attr=selector.slice(1,-1),key=attr.replace(/^data-/,'').replace(/-([a-z])/g,(_,c)=>c.toUpperCase());const elements=[...this._html.matchAll(new RegExp(attr+'="([^"]+)"','g'))].map(match=>{const e=new Element(this.host);e.dataset[key]=match[1];return e;});this.queryCache.set(selector,elements);return elements;}
  scrollIntoView(){}
}
class Host extends Element {constructor(){super(null);this.host=this;this.elements=new Map();this.isConnected=true;}}
class FakeFormData {constructor(){this.values=[];} append(...args){this.values.push(args);}}
global.FormData=FakeFormData;
(async()=>{
  let calls=[],upload=deferred(),activation=deferred(),listValue={available:false,items:[],total:0},isCurrent=true;
  const host=new Host();
  const request=async(path,opts={})=>{calls.push({path,opts});if(path==='/api/catalogue/imports'&&opts.method==='POST')return upload.promise;if(path.endsWith('/activate'))return activation.promise;if(path==='/api/catalogue/imports')return {items:[]};if(path.startsWith('/api/catalogue?'))return listValue;throw Error('Unexpected '+path);};
  const mount=await view.mount(host,request,{isCurrent:()=>isCurrent});
  const el=id=>host.querySelector('#catalogue-'+id);
  assert.ok(el('file'),'empty catalogue retains upload control');
  assert.match(el('summary').innerHTML,/No source catalogue selected/);
  el('file').files=[{name:'example.xlsx',size:100}];el('file').onchange();await delay();
  assert.ok(el('file').disabled);assert.ok(!calls.some(c=>c.path.endsWith('/activate')),'file selection never activates');
  const post=calls.find(c=>c.opts.method==='POST');assert.ok(post.opts.body instanceof FakeFormData);assert.equal(post.opts.body.values[0][0],'file');assert.equal(post.opts.headers,undefined,'browser supplies multipart boundary; api wrapper supplies token');
  upload.resolve(metadata);await delay();await delay();
  assert.equal(el('preview').hidden,false);assert.match(el('preview').innerHTML,/Use in catalogue/);assert.ok(!calls.some(c=>c.path.endsWith('/activate')));
  el('activate').onclick();el('activate').onclick();await delay();
  assert.equal(calls.filter(c=>c.path.endsWith('/activate')).length,1,'double click causes one pending activation');
  const activate=calls.find(c=>c.path.endsWith('/activate'));assert.deepEqual(JSON.parse(activate.opts.body),{expected_active_hash:null});assert.equal(activate.opts.headers['Content-Type'],'application/json');
  listValue=catalogue;activation.resolve({...metadata,active:true});await delay();await delay();
  assert.match(el('message').textContent,/remain unreviewed/);assert.match(el('table').innerHTML,/Alpha/);assert.ok(el('activate').disabled);
  mount.dispose();assert.ok(post.opts.signal.aborted,'route disposal aborts upload lifecycle');

  const staleHost=new Host(),first=deferred(),second=deferred();let loads=0;const pending=[];
  const staleRequest=async(path,opts={})=>{if(path==='/api/catalogue/imports')return {items:[]};if(path.startsWith('/api/catalogue?')){pending.push(opts.signal);return ++loads===1?catalogue:loads===2?first.promise:second.promise;}throw Error(path);};
  const mounted=await view.mount(staleHost,staleRequest);const se=id=>staleHost.querySelector('#catalogue-'+id);
  se('station').value='Old station';se('circle').value='C';se('circle').onchange();assert.equal(se('station').value,'','changing circle clears incompatible station');await delay();se('kind').value='PTR';se('kind').onchange();await delay();
  assert.ok(pending[1].aborted,'superseded list aborted');second.resolve({...catalogue,items:[ptr],total:1});await delay();first.resolve({...catalogue,items:[{...tl,station:'Stale station'}]});await delay();
  assert.ok(!se('table').innerHTML.includes('Stale station'));assert.match(se('table').innerHTML,/PTR/);
  mounted.dispose();


  const conflictHost=new Host(),conflict=deferred();let attempts=[];let refreshedPreview=0;
  const conflictRequest=async(path,opts={})=>{
    if(path==='/api/catalogue/imports'&&opts.method==='POST')return {...metadata,expected_active_hash:'preview-hash'};
    if(path.endsWith('/activate')){attempts.push(JSON.parse(opts.body));return attempts.length===1?conflict.promise:{...metadata,active:true};}
    if(path==='/api/catalogue/imports')return {items:[]};
    if(path.startsWith('/api/catalogue?'))return {...catalogue,catalogue_hash:'newer-list-hash'};
    if(path==='/api/catalogue/imports/'+metadata.import_id){refreshedPreview++;return {...metadata,expected_active_hash:'fresh-preview-hash'};}
    throw Error(path);
  };
  const conflictMount=await view.mount(conflictHost,conflictRequest);const ce=id=>conflictHost.querySelector('#catalogue-'+id);
  ce('file').files=[{name:'example.xlsx',size:100}];ce('file').onchange();await delay();await delay();
  ce('activate').onclick();await delay();assert.deepEqual(attempts,[{expected_active_hash:'preview-hash'}],'activation uses reviewed preview snapshot rather than newer list hash');
  conflict.reject(Error('Catalogue changed. Preview again before selecting.'));await delay();await delay();
  assert.equal(refreshedPreview,1);assert.equal(attempts.length,1,'CAS conflict refreshes preview but never retries activation automatically');
  assert.match(ce('message').textContent,/Catalogue changed/);assert.equal(ce('activate').disabled,false);
  ce('activate').onclick();await delay();await delay();assert.deepEqual(attempts[1],{expected_active_hash:'fresh-preview-hash'},'explicit second click uses refreshed preview snapshot');
  conflictMount.dispose();

  const rowHost=new Host(),rowRead=deferred();let current=true;let rowSignal;
  const rowRequest=async(path,opts={})=>{if(path==='/api/catalogue/imports')return {items:[]};if(path.startsWith('/api/catalogue?'))return catalogue;if(path.startsWith('/api/catalogue/rows/')){rowSignal=opts.signal;return rowRead.promise;}throw Error(path);};
  const rowMount=await view.mount(rowHost,rowRequest,{isCurrent:()=>current});const re=id=>rowHost.querySelector('#catalogue-'+id);
  const rowButton=re('table').querySelectorAll('[data-catalogue-row]')[0];rowButton.onclick();await delay();current=false;rowMount.dispose();rowRead.resolve({...tl,catalogue_hash:'old-hash'});await delay();
  assert.ok(rowSignal.aborted);assert.equal(re('detail').textContent,'Loading source row…');assert.equal(re('detail').innerHTML,'','late row cannot paint a retired route');

  const changedHost=new Host();let changedLoads=0;
  const changedRequest=async(path)=>{
    if(path==='/api/catalogue/imports')return {items:[]};
    if(path.startsWith('/api/catalogue?'))return {...catalogue,catalogue_hash:++changedLoads===1?'old-hash':'replacement-hash'};
    if(path.startsWith('/api/catalogue/rows/'))return {...tl,station:'Wrong version station',catalogue_hash:'replacement-hash'};
    throw Error(path);
  };
  const changedMount=await view.mount(changedHost,changedRequest);const ve=id=>changedHost.querySelector('#catalogue-'+id);
  ve('table').querySelectorAll('[data-catalogue-row]')[0].onclick();await delay();await delay();
  assert.match(ve('message').textContent,/active catalogue changed/);assert.ok(!ve('detail').innerHTML.includes('Wrong version station'));assert.equal(changedLoads,2,'row from a replacement version refreshes list before displaying detail');
  changedMount.dispose();

  console.log('Catalogue UI: bounded upload, preview-only intake, explicit CAS activation, escaped provenance, PTR separation, large filters and stale request guards passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
