'use strict';
const assert=require('node:assert/strict');
const m=require('../src/dranalyser/application/static/instrument-review.js');
const hash='a'.repeat(64),review={record_hash:hash,reviewer:'Engineer',evidence:'Actual instrument schedule',confirmed_secondary:true,ratios:{A1:{primary:1000,secondary:1},A2:{primary:132000,secondary:110},A5:{primary:500,secondary:1}}};
const analog=(id,unit,primary,secondary)=>({id,label:id,kind:'analog',unit,ps:'S',primary,secondary});
const file={name:'LocalStation.cfg',kind:'comtrade',content_hash:hash,channel_inventory:[{...analog('A1','A',1000,1),recorded_primary:1,recorded_secondary:0,instrument_reviewed:true},{...analog('A2','V',132000,110),recorded_primary:1,recorded_secondary:0,instrument_reviewed:true},analog('A3','A',800,1),{...analog('A5','A',500,1),recorded_primary:1,recorded_secondary:0,instrument_reviewed:true}]};
const row={incident_id:'sample',number:3,metadata:{assignments:{[file.name]:{instrument_review:review}}},bundle:{files:[file]}};
const requirements={record:file.name,revision:3,record_hash:hash,applied_review:review,required_ratios:[],reviewable_ratios:[analog('A1','A',1,0),analog('A2','V',1,0),analog('A5','A',1,0)]};
assert.equal(m.missingInstrumentRatings(file).length,0);
const required=m.reviewableInstrumentRatings(row,file,requirements);
assert.deepEqual(required.map(c=>c.id),['A1','A2','A5']);assert.ok(required.every(c=>c.secondary===0));
const html=m.instrumentReviewEditor(row,file.name,{[file.name]:requirements});
assert.match(html,/saved ratings/);assert.ok(html.includes('value="1000"'));assert.ok(html.includes('value="132000"'));assert.ok(html.includes('Actual instrument schedule'));
assert.ok(!html.includes('data-rating="A3"'),'an already valid original ratio is not offered for replacement');
assert.ok(!html.includes('data-rating-confirm checked'),'saving a changed review requires renewed confirmation');
assert.equal(m.appliedInstrumentReview({...row,metadata:{assignments:{[file.name]:{instrument_review:{...review,record_hash:'b'.repeat(64)}}}}},file),null);
const values=m.instrumentFormValues(required,review);
assert.deepEqual(values.common.ct,{primary:1000,secondary:1});assert.equal(values.rows.A5.override,true);assert.equal(values.rows.A1.override,false);
function fixture(channels=required,{loaded=false}={}){
 const fields={},inputs=[];
 const input=(value='',dataset={},tagName='INPUT')=>{const node={value,checked:false,disabled:false,dataset,tagName,handlers:{},addEventListener(event,fn){const previous=this.handlers[event];this.handlers[event]=eventValue=>{previous?.(eventValue);fn(eventValue);};}};inputs.push(node);return node;};
 for(const name of ['ct-primary','ct-secondary','vt-primary','vt-secondary'])fields[`[data-common="${name}"]`]=input('',{common:name});
 fields['[data-rating-reviewer]']=input();fields['[data-rating-evidence]']=input('',{},'TEXTAREA');fields['[data-rating-confirm]']=input();
 const status={textContent:'Waiting'},rows=channels.map(channel=>{
  const nodes={primary:input(),secondary:input(),override:input(),declaration:{textContent:''}},r={dataset:{rating:channel.id,unit:channel.unit==='A'?'A':'V'},nodes,querySelector(selector){return selector==='[data-rating-override]'?nodes.override:selector==='[data-rating-declaration]'?nodes.declaration:selector.includes('primary')?nodes.primary:nodes.secondary;}};
  nodes.primary.disabled=true;nodes.secondary.disabled=true;nodes.override.closest=()=>r;return r;
 });
 const actions=['check','save','download'].map(ratingAction=>({tagName:'BUTTON',dataset:{ratingAction},disabled:false}));
 const section={dataset:{instrumentFile:file.name,...(loaded?{ratingsLoaded:'true'}:{})},isConnected:true,replacement:null,replaceWith(replacement){this.replacement=replacement;this.isConnected=false;},querySelector(selector){return selector==='.instrument-rating-result'?status:fields[selector];},querySelectorAll(selector){
  if(selector==='[data-rating]')return rows;
  const unit=/^\[data-rating\]\[data-unit="([AV])"\]$/.exec(selector);if(unit)return rows.filter(r=>r.dataset.unit===unit[1]);
  if(selector==='input,textarea')return inputs;
  if(selector==='input,textarea,button')return [...inputs,...actions];
  if(selector==='[data-common]')return Object.entries(fields).filter(([key])=>key.startsWith('[data-common=')).map(([,node])=>node);
  if(selector==='[data-rating-override]')return rows.map(r=>r.nodes.override);
  if(selector==='[data-rating-action]')return actions;
  return [];
 }};
 return {section,fields,status,rows,inputs,actions};
}
const form=fixture();m.hydrateInstrumentReview(form.section,required,review);
assert.equal(form.fields['[data-common="ct-primary"]'].value,'1000');assert.equal(form.rows[2].nodes.override.checked,true);
assert.equal(form.rows[2].nodes.primary.value,'500');assert.equal(form.rows[0].nodes.primary.disabled,true);
assert.equal(form.rows[0].nodes.declaration.textContent,'CFG: 1 / 0 A · secondary');
assert.throws(()=>m.collectInstrumentReview(form.section,file),/Confirm/);
form.fields['[data-rating-confirm]'].checked=true;assert.deepEqual(m.collectInstrumentReview(form.section,file),review);
const settle=async()=>{for(let i=0;i<4;i++)await new Promise(done=>setImmediate(done));};
global.location={hash:'#incident/sample'};
(async()=>{
 let request,resolve,reject;global.api=(path,options)=>{request={path,options};return new Promise((done,fail)=>{resolve=done;reject=fail;});};
 let f=fixture(),controller=new AbortController();m.bindInstrumentReview(row,{querySelectorAll:()=>[f.section]},{signal:controller.signal});
 assert.match(request.path,/record=LocalStation.cfg&revision=3$/);resolve(requirements);await settle();assert.equal(f.fields['[data-common="ct-primary"]'].value,'1000');assert.match(f.status.textContent,/Saved ratings loaded/);
 assert.ok(f.actions.every(button=>!button.disabled),'verified requirements enable rating actions');
 f.fields['[data-rating-confirm]'].checked=true;f.fields['[data-common="ct-primary"]'].value='1200';f.fields['[data-common="ct-primary"]'].handlers.input();
 assert.equal(f.fields['[data-rating-confirm]'].checked,false,'editing a universal rating invalidates its earlier confirmation');
 f.fields['[data-rating-confirm]'].checked=true;f.rows[2].nodes.primary.handlers.input();
 assert.equal(f.fields['[data-rating-confirm]'].checked,false,'editing a channel exception invalidates its earlier confirmation');
 f.fields['[data-rating-confirm]'].checked=true;f.rows[2].nodes.override.handlers.change();
 assert.equal(f.fields['[data-rating-confirm]'].checked,false,'changing inheritance invalidates its earlier confirmation');
 f=fixture();m.bindInstrumentReview(row,{querySelectorAll:()=>[f.section]},{});f.fields['[data-common="ct-primary"]'].value='1200';f.fields['[data-common="ct-primary"]'].handlers.input();resolve(requirements);await settle();assert.equal(f.fields['[data-common="ct-primary"]'].value,'1200','a late GET cannot overwrite user edits');
 f=fixture();controller=new AbortController();m.bindInstrumentReview(row,{querySelectorAll:()=>[f.section]},{signal:controller.signal});const pendingStatus=f.status.textContent;controller.abort();f.section.isConnected=false;resolve(requirements);await settle();assert.equal(f.status.textContent,pendingStatus,'aborted response does not touch a detached panel');
 f=fixture();m.bindInstrumentReview(row,{querySelectorAll:()=>[f.section]},{});resolve({...requirements,revision:2});await settle();assert.match(f.status.textContent,/Recording or revision changed/);assert.equal(f.fields['[data-common="ct-primary"]'].value,'');
 assert.equal(f.fields['[data-common="ct-primary"]'].disabled,false,'failed source checks preserve editable draft values');
 assert.ok(f.actions.every(button=>button.disabled),'failed source checks cannot submit unverified channel rows');
 f=fixture();m.bindInstrumentReview(row,{querySelectorAll:()=>[f.section]},{});reject(new Error('Temporary connection failure'));await settle();
 assert.equal(f.fields['[data-rating-reviewer]'].disabled,false,'a failed GET does not leave draft inputs unusable');
 assert.ok(f.actions.every(button=>button.disabled),'a failed GET cannot submit the initial inventory as authoritative');
 assert.match(f.status.textContent,/reopen|retry|try again/i,'failed loading explains how to retry');

 // The original inventory may show 14 secondary channels while only six phase channels
 // need the engineering review. Exercise the live replacement and its action binding.
 const allChannels=Array.from({length:14},(_,index)=>analog('A'+(index+1),index<3?'V':'A',1,0));
 const phaseChannels=allChannels.slice(0,6),phaseFile={...file,channel_inventory:allChannels};
 const phaseRow={...row,metadata:{},bundle:{files:[phaseFile]}},phaseRequirements={record:file.name,revision:row.number,record_hash:hash,applied_review:null,required_ratios:phaseChannels,reviewable_ratios:allChannels};
 f=fixture(allChannels);m.bindInstrumentReview(phaseRow,{querySelectorAll:()=>[f.section]},{});
 f.fields['[data-common="ct-primary"]'].value='1400';f.fields['[data-common="ct-primary"]'].handlers.input();resolve(phaseRequirements);await settle();
 assert.equal(f.fields['[data-common="ct-primary"]'].value,'1400','changed channel requirements do not discard in-flight draft edits');
 assert.equal(f.section.replacement,null,'a changed-channel response does not replace an edited form');
 assert.ok(f.actions.every(button=>button.disabled),'edited inventory cannot submit when the authoritative channel set differs');assert.match(f.status.textContent,/reopen/i);
 f=fixture(allChannels);let replacement;
 global.document={createElement(tag){assert.equal(tag,'div');return {set innerHTML(markup){
  const ids=[...markup.matchAll(/<tr data-rating="([^"]+)"/g)].map(match=>match[1]);
  replacement=fixture(allChannels.filter(channel=>ids.includes(channel.id)),{loaded:markup.includes('data-ratings-loaded="true"')});
 },querySelector(selector){assert.equal(selector,'[data-instrument-file]');return replacement?.section;}};}};
 m.bindInstrumentReview(phaseRow,{querySelectorAll:()=>[f.section]},{});resolve(phaseRequirements);await settle();
 assert.equal(f.section.isConnected,false,'the old 14-channel editor is removed');assert.equal(f.section.replacement,replacement.section);
 assert.deepEqual(replacement.rows.map(r=>r.dataset.rating),phaseChannels.map(c=>c.id),'the live editor contains only the six required phase channels');
 assert.ok(replacement.actions.every(button=>typeof button.onclick==='function'),'replacement actions are rebound');
 Object.assign(replacement.fields['[data-common="ct-primary"]'],{value:'1000'});Object.assign(replacement.fields['[data-common="ct-secondary"]'],{value:'1'});
 Object.assign(replacement.fields['[data-common="vt-primary"]'],{value:'132000'});Object.assign(replacement.fields['[data-common="vt-secondary"]'],{value:'110'});
 replacement.fields['[data-rating-reviewer]'].value='Engineer';replacement.fields['[data-rating-evidence]'].value='Instrument sheet';replacement.fields['[data-rating-confirm]'].checked=true;
 let checked;global.jsonPost=body=>({method:'POST',body:JSON.stringify(body)});global.api=async(path,options)=>{checked=JSON.parse(options.body);return {flags:[],blocked:false};};
 await replacement.actions.find(button=>button.dataset.ratingAction==='check').onclick();
 assert.deepEqual(Object.keys(checked.review.ratios),phaseChannels.map(c=>c.id),'the replacement sends six reviewed channels, excluding auxiliary rows');
 console.log('Saved ratio editing: exact-source reopening, original declarations, confirmation invalidation, failure recovery, late-response guards and 14-to-6 live replacement passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
