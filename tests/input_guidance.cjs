const assert=require('node:assert/strict');
const guidance=require('../src/dranalyser/application/static/input-guidance.js');
const record={blocked:true,flags:['[BLOCK RATIO-P/S] IA 1/0','[BLOCK TIME-DAT] gap','[BLOCK SCALE-CF] VA amplitude']};
const before=JSON.stringify(record),state=guidance.assess(record),html=guidance.markup(record);
assert.equal(state.ratio,true);assert.equal(state.items.length,3);
assert.ok(html.includes('actual primary and secondary'));assert.ok(html.includes('ratio correction does not settle'));
assert.ok(html.includes('Recoverable waveforms can be inspected'));
assert.ok(!html.includes('Waveforms are available.'));
assert.ok(html.includes('data-go-feature="inputs"'));assert.equal(JSON.stringify(record),before);
assert.equal(guidance.markup({blocked:false,flags:[]}), '');
assert.ok(!guidance.markup({blocked:true,flags:['[BLOCK X] <script>x</script>']}).includes('<script>'));

assert.equal(guidance.assess({blocked:true,flags:['[BLOCK RATIO-PS] IA 1/0']}).ratio,true);

const original={name:'original.cfg'},derived={name:'reviewed-ratios-abc123/reviewed.cfg'};
assert.equal(guidance.preferredRecording({metadata:{assignments:{'original.cfg':{role:'excluded'}}}},[original,derived]),derived.name);
assert.equal(guidance.preferredRecording({metadata:{}},[original,derived]),original.name);
