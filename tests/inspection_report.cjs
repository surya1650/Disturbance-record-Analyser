const assert=require('node:assert/strict');
const r=require('../src/dranalyser/application/static/inspection-report.js');
assert.equal(r.number(null),'Not available');assert.equal(r.number(0),'0.0000000');
const html=r.schematic({terminals:{S:'<img src=x>',R:'Not available'},sections:[],location:{status:'Not available',text:'Need line facts'},length_km:null,parameter_status:'Not available',provenance:'No line supplied'});
assert.ok(!html.includes('<img src=x>'));assert.ok(html.includes('&lt;img'));assert.ok(html.includes('Not available'));
const summary=r.summary({snapshot:{sections:{observed:['Source <one>'],supports:['Signals'],cannot_conclude:['Location unknown'],needed_next:['Line facts']},recorded_times:{start:'raw start',trigger:'raw trigger'},inferred_inception:'Not available',line:{terminals:{S:'Not available',R:'Not available'},sections:[],location:{status:'Not available',text:'Need facts'},length_km:null}},assumptions:[{channel_id:'A1',ratio_text:'600/1',source:'user voltage-level default',basis:'unverified'}],scaling_notes:[],trip:{text:'Trip observation'},ar:{text:'Cause unknown'},fit_coverage:{model_consistent:0,total:0,withheld:0},methods:{location:{status:'Not available',reason:'No constants'}}});
assert.ok(summary.includes('600/1'));assert.ok(summary.includes('user voltage-level default'));assert.ok(summary.includes('Source &lt;one&gt;'));assert.ok(summary.includes('raw trigger'));assert.ok(summary.includes('No constants'));
console.log('Snapshot rendering: missing values, explicit assumptions and untrusted labels passed');
const line={name:'Supplied model',length_km:50,terminals:{S:'Not available',R:'Not available'},sections:[],location:{status:'Not available',text:'No stored location'}};
const p={status:'Conditional model projection',distance_km:10,fraction:.2,eligible_overlay:true,method:'reactance model',assumptions:['User selected AB'],authorizes_location:false};
const diagram=r.schematic(line,p);assert.ok(diagram.includes('Approximate line-model projection'));assert.ok(diagram.includes('x1="200"'));assert.ok(diagram.includes('10.000000 km'));
const outside=r.schematic(line,{...p,status:'Outside supplied line',distance_km:100,eligible_overlay:false,reason:'Not clipped'});assert.ok(outside.includes('Not clipped'));assert.ok(!outside.includes('x1="1100"'));
const printResult={options:{fault_loop:'AB',projection_window:0},snapshot:{sections:{observed:['Public source'],supports:['Model'],cannot_conclude:['Physical fault unverified'],needed_next:['Verify assumptions']},recorded_times:{},inferred_inception:'Not available',line,selected_projection:p},assumptions:[],scaling_notes:[],trip:{text:'No recorded trip'},ar:{text:'Not available'},fit_coverage:{model_consistent:6,total:6,withheld:0},methods:{},channels:[{id:'A1',label:'VA',meaning:'VA',units:'V'},{id:'A4',label:'IA',meaning:'IA',units:'A'}],windows:[{index:0,start_index:0,stop_index:96}],derived_quantities:{windows:[{index:0,support_s:[0,.08],sequence:{voltage:{units:'V',zero:[0,0],positive:[10,40],negative:[0,0],basis:'Corresponding source fits'}},loops:{AB:{impedance_ohm:[1,4],basis:'Conditional source scaling'}},projection:p}]}};
const printHtml=r.summary(printResult);assert.ok(printHtml.includes('Conditional phase quantities'));assert.ok(printHtml.includes('4.0000000'));assert.ok(printHtml.includes('A1'));assert.ok(printHtml.includes('0–95'));
// Operator-region selections travel into printable output; technical detail can omit duplicates.
global.DRConditions=require('../src/dranalyser/application/static/inspection-conditions.js');
const op={selection:{source:'operator A/B selection',start:0,end:10,start_s:0,end_s:.01},regions:[{name:'Pre-fault',channels:[]},{name:'Fault',channels:[]},{name:'Post-fault',channels:[]}],overview:[],interpretations:[],note:'operator selected regions'};
const withOperator={...printResult,operator_conditions:op};
assert.ok(r.summary(withOperator).includes('Pre-fault, fault and post-fault conditions'));
assert.ok(!r.summary(withOperator,false).includes('Pre-fault, fault and post-fault conditions'));

// Screen and printable summary consume the same serialized simple report.
global.DRSimpleReport=require('../src/dranalyser/application/static/simple-report.js');
const simpleResult={...printResult,sample_count:96,file:'public.cfg'};
simpleResult.simple_report=global.DRSimpleReport.build(simpleResult);
const simpleHtml=r.summary(simpleResult);
assert.ok(simpleHtml.indexOf('Simple analysis report')<simpleHtml.indexOf('Technical evidence and provenance'));
assert.ok(!r.summary(simpleResult,false).includes('Simple analysis report'));
assert.ok(simpleHtml.includes('Fault interval not selected'));
