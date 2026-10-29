'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const comparison=require('../src/dranalyser/application/static/channel-comparison-model.js');
const inspection=require('../src/dranalyser/application/static/inspection-model.js');
const context=vm.createContext({DRChannelComparison:comparison,DRInspection:inspection,module:{exports:{}}});
vm.runInContext(fs.readFileSync('src/dranalyser/application/static/channel-comparison-view.js','utf8'),context);
const view=context.module.exports;
function host(){
  const input={value:'0'},output={},lines=[],svgs=[];
  return {innerHTML:'',input,output,lines,svgs,querySelector(s){return s==='input'?input:output;},querySelectorAll(s){
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
console.log('Comparison renderer: source-safe rows, readable axes, gaps, shared domain/cursor,128channels, primary order and overlay guard passed');
