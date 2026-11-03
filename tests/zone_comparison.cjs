'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const view=require('../src/dranalyser/application/static/zone-comparison.js');
const root=path.join(__dirname,'../src/dranalyser/application/static');
const comparison={version:1,status:'available',fault_type:'AG',loop:'AG',characteristic_kind:'earth',
  window:{t_start_s:.15,t_end_s:.17,support_count:21,evaluated_count:21},record_hash:'a'.repeat(64),settings_hash:'b'.repeat(64),
  zones:[{name:'Wide',kind:'earth',status:'inside',inside_count:21,outside_count:0,evaluated_count:21,reasons:[]},
    {name:'Narrow',kind:'earth',status:'outside',inside_count:0,outside_count:21,evaluated_count:21,reasons:[]},
    {name:'Crossing',kind:'earth',status:'mixed',inside_count:10,outside_count:11,evaluated_count:21,reasons:[]},
    {name:'Phase only',kind:'earth',status:'not_evaluable',inside_count:0,outside_count:0,evaluated_count:0,reasons:['Earth characteristic not supplied; no phase fallback.']}],
  reasons:[],notes:['Transition screen is inconclusive; this remains a limitation.'],authorizes_operation:false};
const render=value=>view.markup(value,'a'.repeat(64));
const html=render(comparison);
for(const text of ['Reviewed zone-boundary comparison','Classified fault AG · loop AG · earth boundaries',
  'Fixed operational window 0.15 to 0.17 source-local s','Inside','Outside','Mixed','Not evaluable',
  '21 evaluated / 21 candidate phasor supports','<td>0</td>','counts are not independent measurements',
  'Earth characteristic not supplied; no phase fallback.','Transition screen is inconclusive',
  'does not establish zone enablement','selected display loop and cursor do not change'])assert.ok(html.includes(text),text);
assert.ok(!/pass|fail|correct operation/i.test(html),'geometric containment must not become a protection verdict');
assert.ok(html.includes('a'.repeat(64))&&html.includes('b'.repeat(64)));
assert.equal(render({...comparison,display_loop:'BC',cursor_s:900,zoom:[0,10]}),html,'display choices do not change a fixed backend comparison');
const unavailable=render({...comparison,status:'not_evaluable',reasons:['Settings association is ambiguous.'],zones:[]});
assert.match(unavailable,/Comparison not evaluable/);assert.match(unavailable,/Settings association is ambiguous/);
assert.ok(!unavailable.includes('<td>Outside</td>'));
const contradictory=render({...comparison,status:'not_evaluable'});
assert.ok(!contradictory.includes('<td>Inside</td>')&&!contradictory.includes('<td>Outside</td>')&&!contradictory.includes('<td>Mixed</td>'));
assert.match(render(null),/predates zone-boundary comparison.*rerun/);
assert.match(render(undefined),/predates/);
assert.match(render({...comparison,version:2}),/saved comparison version is unsupported/);
assert.ok(!render({...comparison,version:'1'}).includes('<td>Inside</td>'));
const hostile=JSON.parse(JSON.stringify(comparison));
hostile.fault_type='<img src=x onerror=1>';hostile.loop='<svg>';hostile.characteristic_kind='<script>';
hostile.zones[0].name='<script>alert(1)</script>';hostile.zones[0].kind='" onmouseover="bad';hostile.zones[0].reasons=['<img src=x>'];
hostile.reasons=['<svg onload=1>'];hostile.notes=['A & B'];hostile.record_hash='<img src=x>';hostile.settings_hash='" onclick="bad';
hostile.record_hash='a'.repeat(64);
const safe=render(hostile);
assert.ok(!safe.includes('<img')&&!safe.includes('<script')&&!safe.includes('<svg'));
assert.ok(safe.includes('&lt;script&gt;')&&safe.includes('A &amp; B'));
assert.ok(safe.includes('Settings SHA-256 <code style="overflow-wrap:anywhere">Unavailable</code>'));
assert.match(view.markup(comparison,'c'.repeat(64)),/recording identity does not match/);
assert.match(view.markup(comparison),/recording identity does not match/);
assert.ok(!view.markup(comparison,'c'.repeat(64)).includes('<td>Inside</td>'));
const invalidCount=render({...comparison,window:{support_count:Infinity,evaluated_count:-1},zones:[{name:'Invalid saved count',inside_count:'5',outside_count:NaN,evaluated_count:true,status:'unknown'}]});
assert.ok(!invalidCount.includes('Infinity')&&!invalidCount.includes('NaN'));
assert.ok(invalidCount.includes('Unavailable evaluated / Unavailable candidate'));
assert.ok(invalidCount.includes('Not evaluable'));
// The all-relay surface must pass its own record's model, not a selected relay's.
const calls=[];
const context={escapeHtml:s=>String(s??''),mappingEvidence:()=>'',stageClockEvidence:()=>'',rxContextEvidence:()=>'',stageAssociationEvidence:()=>'',DRZoneComparison:{markup:(value,expectedHash)=>{calls.push([value,expectedHash]);return '<p>Shared comparison</p>';}}};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(root,'evidence.js'),'utf8'),context);
const record={record_hash:'a'.repeat(64),status:'analysed',file:'S/event.cfg',end:'S',measurements:{window:{},channels:[]},signals:[],unmapped_digital:[],clipped_channels:[],flags:[],zone_comparison:comparison};
context.relayEvidencePanel({relay_evidence:[record,{...record,file:'R/event.cfg',end:'R',zone_comparison:undefined}],terminal_evidence:[],operation_comparisons:[]});
assert.equal(calls[0][0],comparison);assert.equal(calls[0][1],record.record_hash);assert.equal(calls[1][0],undefined);
const index=fs.readFileSync(path.join(root,'index.html'),'utf8');
assert.ok(index.indexOf('/static/zone-comparison.js')<index.indexOf('/static/evidence.js'),'the shared renderer loads before its consumers');
console.log('Zone-comparison presentation: fixed support, exact states/counts, named abstention, legacy/version handling, record isolation, escaping and script availability passed');
