'use strict';
const assert=require('node:assert/strict');
const m=require('../src/dranalyser/application/static/instrument-review.js');
const current={id:'A1',kind:'analog',label:'IA',unit:'A',ps:'S',primary:1,secondary:0};
const voltage={id:'A2',kind:'analog',label:'VA',unit:'kV',ps:'S',primary:1,secondary:0};
const file={name:'Chandragiri.cfg',kind:'comtrade',ok:false,content_hash:'a'.repeat(64),channel_inventory:[current,voltage,{...current,id:'A3',secondary:1},{...current,id:'A4',ps:''},{id:'D1',kind:'digital'}]};
assert.deepEqual(m.missingInstrumentRatings(file).map(c=>c.id),['A1','A2']);
assert.equal(m.missingInstrumentRatings({channel_inventory:[{...current,unit:undefined,ps:undefined,declared_units:'A',primary_secondary:' S '}]}).length,1);
const row={bundle:{files:[file]}};
let html=m.instrumentReviewEditor(row,'Chandragiri.cfg');
assert.ok(html.includes('data-common="ct-primary"'));assert.ok(html.includes('data-common="vt-primary"'));
assert.equal((html.match(/data-rating="/g)||[]).length,2);
assert.ok(html.includes('Original CFG/DAT/CFF and sample bytes stay unchanged'));
assert.ok(html.includes('Download reviewed COMTRADE ZIP'));
assert.equal(m.instrumentReviewEditor(row,'other.cfg'),'');
html=m.instrumentReviewEditor({bundle:{files:[{...file,channel_inventory:[current]}]}},file.name);
assert.ok(!html.includes('data-common="vt-primary"'),'do not ask VT ratings when only current ratios are missing');
html=m.instrumentReviewEditor({bundle:{files:[{...file,name:'<img src=x>',channel_inventory:[{...current,label:'<script>x</script>'}]}]}});
assert.ok(!html.includes('<img src=x>'));assert.ok(!html.includes('<script>x</script>'));assert.ok(html.includes('&lt;script&gt;'));

assert.ok(html.includes('Universal CT ratings'));
assert.ok(!html.includes('<details class="instrument-common"'),'universal inputs must be visible, not hidden inside a disclosure');
assert.ok(html.includes('<details class="instrument-overrides">'),'individual inputs are optional overrides');
const fields={'[data-rating-reviewer]':{value:'Engineer'},'[data-rating-evidence]':{value:'Actual relay setting export'},'[data-rating-confirm]':{checked:true}};
for(const[k,value]of Object.entries({'ct-primary':'1000','ct-secondary':'1','vt-primary':'220000','vt-secondary':'110'}))fields[`[data-common="${k}"]`]={value};
function rating(id,unit){
 const own={primary:{value:''},secondary:{value:''},override:{checked:false}};
 return {dataset:{rating:id,unit},own,querySelector(q){return q==='[data-rating-override]'?own.override:q.includes('primary')?own.primary:own.secondary;}};
}
const current1=rating('A1','A'),current2=rating('A5','A'),voltage1=rating('A2','V');
const section={querySelector(q){return fields[q];},querySelectorAll(){return [current1,current2,voltage1];}};
let reviewed=m.collectInstrumentReview(section,file);
assert.deepEqual(reviewed,{record_hash:file.content_hash,reviewer:'Engineer',evidence:'Actual relay setting export',confirmed_secondary:true,ratios:{A1:{primary:1000,secondary:1},A5:{primary:1000,secondary:1},A2:{primary:220000,secondary:110}}});
assert.equal(reviewed.ratios.A3,undefined,'valid existing ratios must not be replaced');
// One neutral or separate-core channel can differ without changing other currents.
current2.own.override.checked=true;current2.own.primary.value='500';current2.own.secondary.value='1';
fields['[data-common="ct-primary"]'].value='800';
reviewed=m.collectInstrumentReview(section,file);
assert.deepEqual(reviewed.ratios.A1,{primary:800,secondary:1});assert.deepEqual(reviewed.ratios.A5,{primary:500,secondary:1});
assert.deepEqual(reviewed.ratios.A2,{primary:220000,secondary:110});
current2.own.secondary.value='';assert.throws(()=>m.collectInstrumentReview(section,file),/A5.*actual positive/);current2.own.secondary.value='1';
for(const value of ['', '0','-1','Infinity','1e13']){fields['[data-common="ct-secondary"]'].value=value;assert.throws(()=>m.collectInstrumentReview(section,file),/Universal CT.*actual positive/);}
fields['[data-common="ct-secondary"]'].value='1';fields['[data-common="ct-primary"]'].validity={badInput:true};assert.throws(()=>m.collectInstrumentReview(section,file));delete fields['[data-common="ct-primary"]'].validity;
fields['[data-common="ct-primary"]'].value='1e12';fields['[data-common="ct-secondary"]'].value='1e-9';assert.throws(()=>m.collectInstrumentReview(section,file),/ratio is outside/);
fields['[data-common="ct-primary"]'].value='800';fields['[data-common="ct-secondary"]'].value='1';
fields['[data-rating-confirm]'].checked=false;assert.throws(()=>m.collectInstrumentReview(section,file),/Confirm/);
fields['[data-rating-confirm]'].checked=true;fields['[data-rating-evidence]'].value='';assert.throws(()=>m.collectInstrumentReview(section,file),/reviewer and the source/);
console.log('Instrument review: universal CT/VT inheritance, independent exceptions, valid ratio preservation, strict numeric/evidence checks and source-safe markup passed');
