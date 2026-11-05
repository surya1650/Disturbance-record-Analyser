'use strict';
const assert=require('node:assert/strict');
const {readoutRows,digitalRows,recordClockText,renderReadout,mount,mountSet}=require('../src/dranalyser/report/incident_interaction.js');

const analog={range:[0,.06],plot:{left:10,right:610,top:10,bottom:110},channels:[
  {label:'R',units:'kA',original_units:'A primary',factor:1000,trace:[[10,0,0],[11,.01,1250],[12,.03,-1000]]},
  {label:'Y',units:'V',original_units:'V',trace:[[30,0,10],[31,.02,20],[32,.04,0]]},
  {label:'B',units:'counts',original_units:'counts',factor:1000,trace:[[50,0,1],[51,.01,null],[52,.03,2]]}
]};
let rows=readoutRows(analog,.019);
assert.deepEqual(rows.map(row=>[row.label,row.value,row.units,row.source_time_s,row.sample,row.reason]),[
  ['R',1.25,'kA',.01,11,null],['Y',20,'V',.02,31,null],['B',null,null,null,null,'Gap or no retained support']
],'each phase identifies its own nearest retained sample; a gap remains unavailable');
assert.deepEqual(readoutRows(analog,0).map(row=>row.value),[0,10,1]);
assert.equal(readoutRows({channels:[{label:'Tiny',units:'kA',original_units:'A',factor:1000,trace:[[0,0,1e-323]]}]},0)[0].value,1e-323);
assert.deepEqual(readoutRows({},0),[]);

const digital_inspection={total_channels:6,omitted_channels:2,channel_limit:4,channels:[
  {id:'active-low',label:'Trip <img src=x onerror=bad()>',asserted_state:0,polarity_label:'Low is asserted',omitted_segments:3,segments:[
    {from_s:0,to_s:.01,from_index:0,to_index:1,state:1},
    {from_s:.02,to_s:.03,from_index:2,to_index:3,state:0},
    {from_s:.05,to_s:.05,from_index:5,to_index:5,state:1}],
    window_summary:{active_during_window:true,duration_bounds_s:[.01,.02],censored_start:false,censored_end:true}},
  {id:'unreviewed',label:'Raw only',asserted_state:null,segments:[{from_s:0,to_s:.06,from_index:0,to_index:6,state:1}],
    window_summary:{active_during_window:true,duration_bounds_s:[0,.06],high_duration_bounds_s:[.04,.06],observed_high_span_s:.04}},
  {id:'zero',label:'Zero is recorded',asserted_state:1,segments:[{from_s:0,to_s:.06,from_index:0,to_index:6,state:0}],
    window_summary:{active_during_window:false,duration_bounds_s:[0,0]}},
  {id:'unknown',label:'No support',asserted_state:1,segments:[{from_s:0,to_s:1,state:null}],window_summary:{active_during_window:null,duration_bounds_s:null}}
]};
const payload={...analog,digital_inspection,record_clock:{start_display:'05 Nov 2026 08:00:00.123',trigger_display:'05 Nov 2026 08:00:00.456',
  start_local_iso:'2026-11-05T08:00:00.123',trigger_local_iso:'2026-11-05T08:00:00.456',timezone_label:'Not declared',cursor_time_status:'unavailable',
  reason:'First DAT timestamp was normalized; no absolute cursor anchor.'}};
for(const channel of digital_inspection.channels)channel.window_summary.time_range_s=[.01,.04];
rows=digitalRows(payload,.02);
assert.equal(rows[0].state,0);assert.equal(rows[0].asserted,true);assert.match(rows[0].at_cursor,/Low \(0\) · Asserted/);
assert.equal(rows[0].active_in_window,'Yes');
assert.equal(rows[0].recorded_active_duration,'0.01–0.02 s (recorded portion; boundary censored)','omitted cursor segments do not erase a full-source window summary');
assert.match(digitalRows(payload,.01)[0].at_cursor,/High \(1\) · Cleared/,'the last known sample of a run is supported');
assert.equal(digitalRows(payload,.015)[0].state,null,'the unsampled transition bracket is unknown');
assert.equal(digitalRows(payload,.04)[0].state,null,'known runs never extend across a gap');
assert.equal(digitalRows(payload,.05)[0].state,1,'a singleton supports its exact recorded time');
assert.equal(digitalRows(payload,.050001)[0].state,null,'a singleton never extrapolates');
assert.equal(digitalRows(payload,-.01)[0].state,null);assert.equal(digitalRows(payload,NaN)[0].state,null);
assert.equal(rows[1].asserted,null);assert.match(rows[1].at_cursor,/High \(1\) · polarity unreviewed/);
assert.equal(rows[1].active_in_window,'Unknown polarity');assert.equal(rows[1].recorded_active_duration,'High span 0.04–0.06 s; active unverified');
const rawFallback={digital_inspection:{channels:[{asserted_state:null,window_summary:{observed_high_span_s:.04}}]}};
assert.equal(digitalRows(rawFallback,0)[0].recorded_active_duration,'Observed high span ≥0.04 s; active unverified');
rawFallback.digital_inspection.channels[0].window_summary.observed_high_span_s=0;
assert.equal(digitalRows(rawFallback,0)[0].recorded_active_duration,'Observed high span 0 s; active unverified');
assert.equal(rows[2].state,0);assert.equal(rows[2].asserted,false);assert.equal(rows[2].active_in_window,'No');assert.equal(rows[2].recorded_active_duration,'0 s');
assert.equal(rows[3].state,null);assert.equal(rows[3].active_in_window,'Unknown');assert.equal(rows[3].recorded_active_duration,'Unknown');
const limited=structuredClone(payload);
limited.digital_inspection.channels[1].window_summary.censored_start=true;
limited.digital_inspection.channels[1].window_summary.gap_count=1;
limited.digital_inspection.channels[1].window_summary.reason='Missing observations limit this sampled-state bracket.';
assert.match(digitalRows(limited,.02)[1].recorded_active_duration,/boundary censored; missing observations/);
assert.equal(digitalRows(limited,.02)[1].support_reason,'Missing observations limit this sampled-state bracket.');
assert.deepEqual(digitalRows({},0),[]);
assert.equal(digitalRows({digital_inspection:{channels:[{asserted_state:false,segments:[{from_s:0,to_s:1,state:0}]}]}},0)[0].asserted,null,'only explicit numeric reviewed polarity is accepted');
assert.match(recordClockText({}),/Record clock unavailable.*source-local elapsed/);
assert.match(recordClockText(payload),/Record start: 05 Nov 2026 08:00:00.123 · Trigger: 05 Nov 2026 08:00:00.456 · Time zone: Not declared/);
assert.match(recordClockText(payload),/Cursor clock unavailable/);
assert.ok(!recordClockText(payload).includes('UTC'));assert.ok(!recordClockText(payload).includes('IST'));
assert.match(recordClockText({record_clock:{start_local_iso:'2026-11-05T08:00:00'}}),/Record start: Unavailable/,'an ISO field alone is never guessed into a display clock');

class Element{
  constructor(tag,doc){this.tagName=tag;this.ownerDocument=doc;this.children=[];this.attributes={};this.dataset={};this.handlers={};this._text='';}
  set textContent(text){this._text=String(text);this.children=[];}
  get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
  set innerHTML(_){throw new Error('Source data must never be parsed as HTML');}
  setAttribute(key,value){this.attributes[key]=String(value);}
  hasAttribute(key){return key in this.attributes;}
  append(...children){this.children.push(...children);}
  addEventListener(key,fn){(this.handlers[key]??=[]).push(fn);}
  emit(key,event={}){for(const fn of this.handlers[key]||[])fn(event);}
  dispatchEvent(event){this.emit(event.type,event);}
}
const doc={createElement:tag=>new Element(tag,doc)};
const descendants=(node,tag)=>node.children.flatMap(child=>[...(child.tagName===tag?[child]:[]),...descendants(child,tag)]);
const output=doc.createElement('div');
renderReadout(output,payload,.019);
assert.equal(output.attributes.role,'status');assert.equal(output.attributes['aria-live'],'polite');assert.equal(output.attributes['aria-atomic'],'true');
const tables=descendants(output,'table');assert.equal(tables.length,2);
assert.equal(tables[0].attributes.class,'waveform-readout-table');assert.equal(tables[1].attributes.class,'waveform-digital-table');
assert.deepEqual(descendants(tables[0],'thead')[0].children[0].children.map(node=>node.textContent),['Phase','Instantaneous value','Source local s','Sample']);
const body=descendants(tables[0],'tbody')[0];
assert.deepEqual(body.children[0].children.map(node=>node.textContent),['R','1.25 kA (1250 A primary)','0.01','11']);
assert.deepEqual(body.children[1].children.map(node=>node.textContent),['Y','20 V','0.02','31']);
assert.deepEqual(body.children[2].children.map(node=>node.textContent),['B','Unavailable (gap or no retained support)','—','—']);
assert.equal(body.children[0].children[0].attributes.scope,'row');
assert.ok(output.textContent.includes('Trip <img src=x onerror=bad()>'));assert.equal(descendants(output,'img').length,0);
assert.ok(output.textContent.includes('nearest retained observation; no interpolation'));
assert.ok(output.textContent.includes('selected window 0.01–0.04 local s'));
assert.ok(output.textContent.includes('2 signals omitted; 3 segments omitted'));
assert.ok(output.textContent.includes('05 Nov 2026 08:00:00.123'));
renderReadout(output,limited,.02);
assert.equal(descendants(descendants(output,'table')[1],'tbody')[0].children[1].attributes.title,'Missing observations limit this sampled-state bracket.');
renderReadout(output,{...analog,channels:[{label:'<script>bad()</script>',units:'<svg onload=bad()>',original_units:'<svg onload=bad()>',trace:[[0,0,0]]}]},0);
assert.equal(descendants(output,'table').length,1,'changing the payload replaces previous tables');
assert.ok(output.textContent.includes('<script>bad()</script>'));assert.equal(descendants(output,'script').length,0);assert.equal(descendants(output,'svg').length,0);

const cursor=doc.createElement('line'),json=doc.createElement('script');json.textContent=JSON.stringify(payload);
const svg=doc.createElement('svg');svg.querySelector=()=>cursor;svg.getScreenCTM=()=>({inverse(){return {};}});
svg.createSVGPoint=()=>({matrixTransform(){return {x:this.x,y:this.y};}});
const view=doc.createElement('div');view.querySelector=selector=>selector==='svg.waveform'?svg:selector==='.waveform-readout'?output:selector==='.waveform-data'?json:null;
mount(view);mount(view);assert.equal(view.handlers.keydown.length,1);
const press=key=>view.emit('keydown',{key,preventDefault(){}});
press('Home');assert.equal(descendants(output,'table').length,2);assert.ok(output.textContent.includes('0 kA (0 A primary)'));
press('ArrowRight');assert.equal(descendants(descendants(output,'table')[0],'tbody')[0].children[0].children[2].textContent,'0.01');
svg.emit('pointerdown',{clientX:210,clientY:50,pointerType:'touch'});const held=output.textContent;
svg.emit('pointerleave',{pointerType:'touch'});assert.equal(output.textContent,held);
svg.emit('pointerleave',{pointerType:'mouse'});assert.equal(descendants(output,'table').length,0);assert.match(output.textContent,/Hover or touch/);
press('End');assert.equal(cursor.attributes.visibility,'visible');press('Escape');assert.equal(cursor.attributes.visibility,'hidden');
press('Home');view.emit('blur');assert.equal(descendants(output,'table').length,0);
const focusButton=doc.createElement('button'),overviewButton=doc.createElement('button');
focusButton.dataset.waveformModeButton='focus';overviewButton.dataset.waveformModeButton='overview';
const focusPanel=doc.createElement('div'),overviewPanel=doc.createElement('div');
focusPanel.dataset.waveformMode='focus';overviewPanel.dataset.waveformMode='overview';focusPanel.querySelectorAll=()=>[view];overviewPanel.querySelectorAll=()=>[];
const set=doc.createElement('div');set.querySelectorAll=selector=>selector==='[data-waveform-mode-button]'?[focusButton,overviewButton]:[focusPanel,overviewPanel];
mountSet(set);press('Home');overviewButton.emit('click');assert.equal(descendants(output,'table').length,0);assert.equal(cursor.attributes.visibility,'hidden');
assert.equal(focusPanel.hidden,true);assert.equal(overviewPanel.hidden,false);
json.textContent=JSON.stringify({...payload,range:[.01,.04],channels:[],digital_inspection:{channels:[
  {...digital_inspection.channels[0],segments:[{from_s:-1,to_s:-.5,state:1},{from_s:.02,to_s:.03,state:0},{from_s:1,to_s:2,state:1}]}]}});
press('Home');assert.ok(output.textContent.includes('at cursor 0.02 local s'),'digital keyboard endpoints outside this chart range do not capture Home');
press('End');assert.ok(output.textContent.includes('at cursor 0.03 local s'));
console.log('Incident cursor tables: exact row samples, safe DOM, digital polarity/gaps, clock context and input resets passed');
