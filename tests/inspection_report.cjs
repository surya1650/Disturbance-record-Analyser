const assert=require('node:assert/strict');
const r=require('../src/dranalyser/application/static/inspection-report.js');
assert.equal(r.number(null),'Not available');assert.equal(r.number(0),'0.0000000');
const html=r.schematic({terminals:{S:'<img src=x>',R:'Not available'},sections:[],location:{status:'Not available',text:'Need line facts'},length_km:null,parameter_status:'Not available',provenance:'No line supplied'});
assert.ok(!html.includes('<img src=x>'));assert.ok(html.includes('&lt;img'));assert.ok(html.includes('Not available'));
const summary=r.summary({snapshot:{sections:{observed:['Source <one>'],supports:['Signals'],cannot_conclude:['Location unknown'],needed_next:['Line facts']},recorded_times:{start:'raw start',trigger:'raw trigger'},inferred_inception:'Not available',line:{terminals:{S:'Not available',R:'Not available'},sections:[],location:{status:'Not available',text:'Need facts'},length_km:null}},assumptions:[{channel_id:'A1',ratio_text:'600/1',source:'user voltage-level default',basis:'unverified'}],scaling_notes:[],trip:{text:'Trip observation'},ar:{text:'Cause unknown'},fit_coverage:{model_consistent:0,total:0,withheld:0},methods:{location:{status:'Not available',reason:'No constants'}}});
assert.ok(summary.includes('600/1'));assert.ok(summary.includes('user voltage-level default'));assert.ok(summary.includes('Source &lt;one&gt;'));assert.ok(summary.includes('raw trigger'));assert.ok(summary.includes('No constants'));
console.log('Snapshot rendering: missing values, explicit assumptions and untrusted labels passed');
