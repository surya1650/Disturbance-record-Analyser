'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const comparison=require('../src/dranalyser/application/static/channel-comparison-model.js');
const inspection=require('../src/dranalyser/application/static/inspection-model.js');
const context=vm.createContext({DRChannelComparison:comparison,DRInspection:inspection,module:{exports:{}}});
vm.runInContext(fs.readFileSync('src/dranalyser/application/static/channel-comparison-view.js','utf8'),context);
const view=context.module.exports;
function host(){
  const input={value:'0'},output={},lines=[],svgs=[];
  const controls={};
  for(const id of ['play','reset','speed','playback-status'])controls[id]={value:id==='speed'?'0.25':'',setAttribute(k,v){this[k]=v;}};
  return {innerHTML:'',input,output,lines,svgs,controls,querySelector(s){if(s==='input')return input;if(s==='output')return output;const id=s.match(/^\[data-comparison-(.*?)\]$/)?.[1];return controls[id];},querySelectorAll(s){
    if(s==='.comparison-cursor'){
      while(lines.length<(this.innerHTML.match(/class="comparison-cursor"/g)||[]).length)lines.push({setAttribute(k,v){this[k]=v;}});
      return lines;
    }
    if(s==='svg'){
      while(svgs.length<(this.innerHTML.match(/<svg /g)||[]).length)svgs.push({getBoundingClientRect(){return {left:10,width:200};}});
      return svgs;
    }return [];
  }};
}
const c=(id,label,units)=>({id,label,units,kind:'analog',trace:[[0,0,-10],[1,.01,null],[2,.02,10]]});
const left={file:'<script>alert(1)</script>.cfg',sample_count:3,time_range_s:[0,.02],time_basis:{minimum_interval_s:.01},channels:[c('A1','IA','A'),c('A2','VA','V')]};
const right={file:'remote.cfg',sample_count:5,time_range_s:[2,2.04],time_basis:{minimum_interval_s:.01},channels:[c('A7','VA','kV')]};
right.channels[0].trace=right.channels[0].trace.map(p=>[p[0],p[1]+2,p[2]]);
const before=JSON.stringify([left,right]);
const h=host();view.mount(h,left,right);
assert.equal(JSON.stringify([left,right]),before,'rendering must not mutate source metadata/traces');
assert.ok(h.innerHTML.indexOf('data-quantity="voltage"')<h.innerHTML.indexOf('data-quantity="current"'));
assert.equal((h.innerHTML.match(/data-channel-id=/g)||[]).length,3);
assert.equal((h.innerHTML.match(/comparison-missing/g)||[]).length,1);
assert.ok(h.innerHTML.includes('&lt;script&gt;alert(1)&lt;/script&gt;.cfg'));
assert.ok(!h.innerHTML.includes('<script>'));
assert.ok(h.innerHTML.includes('unverified scaling'));
assert.ok(h.innerHTML.includes('comparison-ylabels'));
assert.ok(h.innerHTML.includes('independent amplitude scale'));
assert.ok(h.innerHTML.includes('this does not align physical events or clocks'));
const broken=[...h.innerHTML.matchAll(/d="M0,133 M([^,]+),23"/g)];
assert.ok(broken.some(m=>Math.abs(Number(m[1])-255)<1e-8),'missing sample breaks path and shorter source stays shorter');
h.input.value='500';h.input.oninput();
assert.ok(h.lines.every(l=>l.x1==='255'&&l.x2==='255'));
assert.equal(h.output.value,'20 ms from each start');
h.svgs[0].onpointermove({clientX:160});assert.ok(h.lines.every(l=>l.x1==='382.5'));
const axis=view.axis([left,right]);assert.equal(axis.timed,true);assert.equal(axis.coordinate([0,2.01,0],right).toFixed(2),'0.01');
assert.equal(axis.span.toFixed(2),'0.04');
const missingTime={...right,time_range_s:null};
assert.equal(view.axis([left,missingTime]).timed,false);
assert.equal(view.axis([left,missingTime]).span,4);
assert.equal(view.axis([left,missingTime]).coordinate([3,null,0],missingTime),3);
const fallback=host();view.mount(fallback,left,missingTime);assert.ok(fallback.innerHTML.includes('zero-based sample index'));
const large={...left,channels:Array.from({length:64},(_,i)=>c('A'+(i+1),'Auxiliary '+i,i%2?'A':'V'))};
const stress=host();view.mount(stress,large,{...large,file:'other.cfg'});
assert.equal((stress.innerHTML.match(/data-channel-id=/g)||[]).length,128);
assert.equal((stress.innerHTML.match(/<svg /g)||[]).length,128);
const empty=host();view.mount(empty,{...left,channels:[]},{...right,channels:[]});assert.ok(empty.innerHTML.includes('No recoverable analog'));
// The primary workbench uses the same default ordering while retaining source IDs.
const ordered=inspection.create({...left,channels:[c('A1','IA','A'),c('A2','VB','V'),c('A3','VA','V'),{id:'D1',kind:'digital',units:'state'}]});
assert.deepEqual(ordered.order,['A3','A2','A1','D1']);
const rawChannels=[c('A1','IA','raw counts'),c('A2','VA','raw counts')];
assert.deepEqual(inspection.groupChannels(rawChannels,{groups:{A1:'1',A2:'1'}}).map(g=>g.map(c=>c.id)),[['A1'],['A2']]);
assert.equal(inspection.phaseFor({label:'VB',phase:'B',units:'V'},[{label:'IR',phase:'R',units:'A'},{label:'VB',phase:'B',units:'V'}]),'B');
// Digital spans come from exact, bounded source metadata, never sample filling.
const digital=(id,label,changes,spans=[])=>({id,label,kind:'digital',units:'state',trace:[],activity:{transition_count:changes,high_intervals:spans,unknown_samples:2,omitted_intervals:0}});
const one={start_index:10,last_index:15,start_s:.01,last_s:.015},two={start_index:20,last_index:20,start_s:.02,last_s:.02};
const withDigital={...left,channels:[...left.channels,digital('D1','Constant <open>',0),digital('D2','Trip indication',2,[one,two]),...Array.from({length:4},(_,i)=>digital('D'+(i+3),'Other '+i,1))]};
const hd=host();view.mount(hd,withDigital,right);
assert.equal((hd.innerHTML.match(/data-digital-channel=/g)||[]).length,6);
assert.ok(hd.innerHTML.indexOf('data-digital-channel="D2"')<hd.innerHTML.indexOf('data-digital-channel="D1"'),'changed channels are listed before constant channels');
assert.ok(hd.innerHTML.includes('Show 2 additional digital channels'));
assert.ok(hd.innerHTML.includes('Constant &lt;open&gt;'));
assert.ok(hd.innerHTML.includes('not verified assertion polarity'));
assert.ok(hd.innerHTML.includes('No digital channels were recorded in this source'));
const digitalHtml=view.digitalTrack(withDigital.channels[3],withDigital,view.axis([withDigital,right]));
assert.equal((digitalHtml.match(/<rect /g)||[]).length,1,'known high span is bounded by its first and last observed sample');
assert.equal((digitalHtml.match(/<circle /g)||[]).length,1,'single high sample stays a point, not an invented pulse width');
assert.ok(!digitalHtml.includes('<path'),'gaps and unknown low intervals are never joined');
assert.ok(hd.innerHTML.indexOf('comparison-playback')<hd.innerHTML.indexOf('comparison-group'),'playback controls stay above all channels');
// Deterministic frame scheduler tests lifecycle and source-local shared playback.
const scheduled=new Map();let next=0,visible=true;
const options={requestFrame(fn){scheduled.set(++next,fn);return next;},cancelFrame(id){scheduled.delete(id);},visible:()=>visible};
const hp=host(),long={...left,time_range_s:[0,2],sample_count:2001},remote={...right,time_range_s:[100,101],sample_count:1001};
const player=view.mount(hp,long,remote,{}, {},options),advance=time=>{const [id,fn]=scheduled.entries().next().value;scheduled.delete(id);fn(time);};
player.play();player.play();assert.equal(scheduled.size,1,'rapid Play requests cannot create competing loops');
advance(0);advance(250);assert.equal(player.position(),.03125);
assert.equal(hp.controls.play['aria-pressed'],'true');assert.equal(hp.output.value,'62.50 ms from each start');
visible=false;advance(500);assert.equal(scheduled.size,0,'hidden comparison pauses and releases its animation frame');
assert.equal(hp.controls.play['aria-pressed'],'false');
visible=true;player.play();assert.equal(scheduled.size,1);player.destroy();assert.equal(scheduled.size,0,'replacing sources destroys pending playback');
player.play();assert.equal(scheduled.size,0,'destroyed sources cannot resume');
const abort=new AbortController(),ha=host(),aborted=view.mount(ha,long,remote,{}, {},{...options,signal:abort.signal});
aborted.play();assert.equal(scheduled.size,1);abort.abort();assert.equal(scheduled.size,0,'revision/source abort cancels playback');
const untimed=host(),manual=view.mount(untimed,long,{...remote,time_range_s:null},{},{},options);
manual.play();assert.equal(scheduled.size,0);assert.equal(untimed.controls.play.disabled,true);
assert.match(untimed.controls['playback-status'].textContent,/requires usable times/);
console.log('Comparison renderer: source-safe rows, readable axes, gaps, shared domain/cursor,128channels, primary order and overlay guard passed');
