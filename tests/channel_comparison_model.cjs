const assert=require('node:assert/strict');
const model=require('../src/dranalyser/application/static/channel-comparison-model.js');
const channel=(id,label,units='A',phase='')=>({id,label,units,phase,kind:'analog',trace:[[0,0,1]]});
const record=channels=>({channels,inventory:[],sample_count:3,file:'synthetic.cfg'});
const rows=groups=>groups.flatMap(g=>g.rows);
const pairIds=groups=>rows(groups).map(r=>[r.meaning,r.left?.id||null,r.right?.id||null]);
const left=record([channel('A1','IA'),channel('A2','IB'),channel('A3','IC'),channel('A4','3IO'),
  channel('A5','Ua','V'),channel('A6','Ub','V'),channel('A7','Uc','V'),channel('A8','VN','V'),
  channel('A9','Auxiliary frequency','Hz')]);
const right=record([channel('A1','VA','V'),channel('A2','VB','V'),channel('A3','VC','V'),channel('A4','VN','V'),
  channel('A5','IA'),channel('A6','IB'),channel('A7','IC'),channel('A8','IN'),channel('A9','VAB','V'),channel('A10','DC auxiliary','A')]);
const before=JSON.stringify([left,right]);
const groups=model.plan(left,right),all=rows(groups);
assert.deepEqual(groups.map(g=>g.quantity),['voltage','other','current']);
assert.ok(all.some(r=>r.meaning==='VA'&&r.left?.id==='A5'&&r.right?.id==='A1'));
assert.ok(all.some(r=>r.meaning==='IA'&&r.left?.id==='A1'&&r.right?.id==='A5'));
assert.ok(all.some(r=>r.meaning==='3I0'&&r.left?.id==='A4'&&!r.right));
assert.ok(all.some(r=>r.meaning==='IN'&&r.right?.id==='A8'&&!r.left));
assert.ok(all.some(r=>r.meaning==='VAB'&&r.right?.id==='A9'&&!r.left));
assert.equal(all.filter(r=>r.left).length,9);assert.equal(all.filter(r=>r.right).length,10);
assert.equal(new Set(all.filter(r=>r.left).map(r=>r.left.id)).size,9);
assert.equal(new Set(all.filter(r=>r.right).map(r=>r.right.id)).size,10);
assert.equal(all.find(r=>r.meaning==='VA').left,left.channels[4]);
assert.equal(JSON.stringify([left,right]),before);
assert.deepEqual(pairIds(model.plan(record([...left.channels].reverse()),record([...right.channels].reverse()))),pairIds(groups));
assert.deepEqual(model.plan(left,null).flatMap(g=>g.rows).map(r=>r.left.id),['A5','A6','A7','A8','A9','A1','A2','A3','A4']);

// Labels alone never disambiguate duplicate sources or manufacture a counterpart.
let result=rows(model.plan(record([channel('A1','IA'),channel('A2','IA')]),record([channel('A7','IA')])));
assert.equal(result.length,3);assert.ok(result.every(r=>!r.left||!r.right));
assert.ok(result.every(r=>/Duplicate/.test(r.reason)));
result=rows(model.plan(record([channel('A1','IA+IB'),channel('A2','IA-IB'),channel('A3','IN (3I0)')]),record([channel('A4','IA')])));
assert.equal(result.length,4);assert.ok(result.every(r=>!r.left||!r.right));
assert.ok(result.filter(r=>r.left).every(r=>/Multiple/.test(r.reason)));

// Token boundaries, units and direct header conflicts are visible, never repaired.
result=rows(model.plan(record([channel('A1','Feeder/IA'),channel('A2','Bay_IL2'),channel('A3','BUS_IL3')]),record([channel('A7','IA'),channel('A8','IB'),channel('A9','IC')])));
assert.equal(result.length,3);assert.ok(result.every(r=>r.left&&r.right));
result=rows(model.plan(record([channel('A1','VA','A'),channel('A2','IB','A','C')]),record([channel('A7','VA','V'),channel('A8','IB')])));
assert.equal(result.length,4);assert.ok(result.every(r=>!r.left||!r.right));
assert.match(result.find(r=>r.left?.id==='A1').reason,/units disagree/);
assert.match(result.find(r=>r.left?.id==='A2').reason,/phase disagree/);
result=rows(model.plan(record([channel('A1','Bay current','A','A')]),record([channel('A7','IA','kA')])));
assert.equal(result.length,1);assert.equal(result[0].meaning,'IA');

// Distinct neutral, zero-sequence, line-to-line and measurement types stay distinct.
result=rows(model.plan(record([channel('A1','IN'),channel('A2','I0'),channel('A3','3I0'),channel('A4','VA RMS','V'),channel('A5','VAB','V')]),
  record([channel('A6','3I0'),channel('A7','IN'),channel('A8','I0'),channel('A9','VA','V'),channel('A10','VBA','V')])));
assert.equal(result.length,7);assert.equal(result.filter(r=>r.left&&r.right).length,3);
assert.ok(result.filter(r=>r.meaning==='VA').every(r=>!r.left||!r.right));
assert.ok(result.filter(r=>['VAB','VBA'].includes(r.meaning)).every(r=>!r.left||!r.right));
result=rows(model.plan(record([channel('A1','IARMS','A','A')]),record([channel('A7','IA','A','A')])));
assert.equal(result.length,2);assert.ok(result.some(r=>r.label==='IA · RMS'));
result=rows(model.plan(record([channel('A1','VA','V (RMS)','A')]),record([channel('A7','VA','V','A')])));
assert.equal(result.length,2);assert.ok(result.some(r=>r.label==='VA · RMS'));

// R/Y/B source convention maps consistently, without changing stored observations.
const ryb=record([channel('A1','VR','V','R'),channel('A2','VY','V','Y'),channel('A3','VB','V','B')]);
result=rows(model.plan(ryb,record([channel('A7','VA','V','A'),channel('A8','VB','V','B'),channel('A9','VC','V','C')])));
assert.deepEqual(result.map(r=>[r.meaning,r.left.id,r.right.id]),[['VA','A1','A7'],['VB','A2','A8'],['VC','A3','A9']]);
result=rows(model.plan(record([channel('A1','IA','A','R'),channel('A2','IB','A','Y'),channel('A3','IC','A','B')]),
  record([channel('A7','IA'),channel('A8','IB'),channel('A9','IC')])));
assert.equal(result.length,3);assert.ok(result.every(r=>r.left&&r.right));

// Explicit display choices can identify counts, but never change numeric units.
const counts=record([channel('A1','unmapped','raw counts')]);
result=rows(model.plan(counts,record([channel('A7','IA')])));assert.equal(result.length,2);
result=rows(model.plan(counts,record([channel('A7','IA')]),{A1:'IA'}));
assert.equal(result.length,1);assert.equal(result[0].left.units,'raw counts');
result=rows(model.plan(record([channel('A1','IA')]),record([channel('A7','IA')]),{A1:'ignore'}));
assert.equal(result.length,2);assert.match(result.find(r=>r.left).reason,/ignored/);
result=rows(model.plan(record([channel('A1','IB')]),record([channel('A7','IA')]),{A1:'IA'}));
assert.equal(result.length,2);assert.match(result.find(r=>r.left).reason,/conflicts with the source/);
result=rows(model.plan(record([channel('A1','IA','A')]),record([channel('A7','VA','V')]),{A1:'VA'}));
assert.equal(result.length,2);assert.ok(result.every(r=>!r.left||!r.right));
result=rows(model.plan(record([channel('A1','Frequency','Hz')]),record([channel('A7','VA','V')]),{A1:'VA'}));
assert.equal(result.length,2);assert.match(result.find(r=>r.left).reason,/units disagree/);

// Phase naming conventions are scoped by quantity; one R-phase current must not
// reinterpret a B-phase voltage as C. Mixed conventions are not silently chosen.
result=rows(model.plan(record([channel('A1','IR'),channel('A2','VB','V')]),
  record([channel('A7','IA'),channel('A8','VB','V'),channel('A9','VC','V')])));
assert.ok(result.some(r=>r.meaning==='VB'&&r.left?.id==='A2'&&r.right?.id==='A8'));
result=rows(model.plan(record([channel('A1','Auxiliary','A','PRIMARY'),channel('A2','IB','A','B')]),
  record([channel('A7','IB','A','B'),channel('A8','IC','A','C')])));
assert.ok(result.some(r=>r.meaning==='IB'&&r.left?.id==='A2'&&r.right?.id==='A7'));
assert.ok(!result.some(r=>r.left?.id==='A2'&&r.right?.id==='A9'));
result=rows(model.plan(record([channel('A1','Current','A','R'),channel('A2','Voltage','V','B')]),
  record([channel('A7','IA'),channel('A8','VB','V'),channel('A9','VC','V')])));
assert.ok(result.some(r=>r.meaning==='VB'&&r.left?.id==='A2'&&r.right?.id==='A8'));
result=rows(model.plan(record([channel('A1','VR','V'),channel('A2','VA','V'),channel('A3','VB','V')]),
  record([channel('A7','VA','V'),channel('A8','VB','V'),channel('A9','VC','V')])));
assert.ok(result.filter(r=>r.left).every(r=>!r.right&&/Mixed/.test(r.reason)));
result=rows(model.plan(record([channel('A1','Voltage','V','R'),channel('A2','Voltage','V','A'),channel('A3','Voltage','V','B')]),
  record([channel('A7','VA','V'),channel('A8','VB','V'),channel('A9','VC','V')])));
assert.ok(result.filter(r=>r.left).every(r=>!r.right&&/Mixed/.test(r.reason)));

// A canonical source-analysis role is not permission to collapse distinguishable
// source measurements (3I0 vs IN, line-line vs phase-neutral, reversed phase order).
for(const[sourceLabel,sourceUnits,target]of [['3I0','A','IN'],['VAB','V','VA'],['VBA','V','VAB'],['I0','A','3I0']]){
  result=rows(model.plan(record([channel('A1',sourceLabel,sourceUnits)]),record([channel('A7',target,sourceUnits)]),{A1:target}));
  assert.equal(result.length,2);assert.ok(result.every(r=>!r.left||!r.right));
  assert.match(result.find(r=>r.left).reason,/conflicts with the source/);
}

// Every analog remains visible at the supported two-record channel limit.
const large=record(Array.from({length:64},(_,i)=>channel('A'+(i+1),'Auxiliary '+i,i%2?'A':'V')));
large.channels.push({id:'D1',label:'TRIP',kind:'digital',units:'state'});
result=rows(model.plan(large,large));
assert.equal(result.length,128);
assert.equal(result.filter(r=>r.left).length,64);assert.equal(result.filter(r=>r.right).length,64);
assert.equal(new Set(result.map(r=>r.key)).size,128);
assert.deepEqual(model.plan(null,null),[]);
assert.equal(model.identify(channel('A1','IA'),record([])).quantity,'current');
console.log('Channel comparison: reordered quantities, all channels, duplicates, conflicts, qualifiers, phases and64-channel sources passed');

// IEC numeric phase names are not reinterpreted by neighboring R/Y/B names.
for(const label of ['IL2','I2']){
  const local=record([channel('A1','IR','A'),channel('A2',label,'A')]);
  const remote=record([channel('A7','IB','A')]);
  const paired=rows(model.plan(local,remote)).find(r=>r.left?.id==='A2');
  assert.equal(paired.meaning,'IB');assert.equal(paired.right?.id,'A7');
}
